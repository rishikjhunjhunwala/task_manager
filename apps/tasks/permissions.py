"""
Permission helpers for tasks app.

Role-based access control for task operations:
- Admin: Full access to all tasks
- Senior Manager 1/2: View all tasks, assign to anyone
- Manager: View department tasks, assign within department
- Employee: View own tasks only, create personal tasks only
"""

from django.db.models import Q
from .models import Task


# =============================================================================
# View Permissions
# =============================================================================

def get_allowed_status_transitions(task, user):
    """
    Get list of status values this task can transition to.
    
    Used by Kanban drag-and-drop to determine valid drop targets.
    """
    from .models import Task
    
    allowed = []
    
    # Check if user can change this task's status at all
    if not can_change_task_status(user, task):
        return allowed
    
    # Get current status
    current_status = task.status
    
    # Terminal states - no transitions allowed
    if current_status in [Task.Status.CANCELLED, Task.Status.VERIFIED]:
        return allowed
    
    # Personal completed tasks are terminal
    if task.is_personal and current_status == Task.Status.COMPLETED:
        return allowed
    
    # Define valid forward transitions
    transitions = {
        Task.Status.PENDING: [Task.Status.IN_PROGRESS],
        Task.Status.IN_PROGRESS: [Task.Status.COMPLETED],
        Task.Status.COMPLETED: [Task.Status.VERIFIED] if task.is_delegated else [],
    }
    
    # Get allowed transitions for current status
    allowed = transitions.get(current_status, [])
    
    # For verification, only creator/admin can verify
    if Task.Status.VERIFIED in allowed:
        if not (user == task.created_by or user.is_admin()):
            allowed.remove(Task.Status.VERIFIED)
    
    return allowed


def can_change_task_status(user, task):
    """
    Check if user can change the status of a task.
    """
    # Admin can change anything
    if user.is_admin():
        return True
    
    # Assignee can progress their own tasks
    if user == task.assignee:
        return True
    
    # Creator can verify delegated tasks
    if user == task.created_by and task.is_delegated:
        return True
    
    return False


def get_visible_tasks(user):
    """
    Get queryset of tasks visible to this user based on their role.
    """
    from .models import Task
    
    base_qs = Task.objects.all()
    
    # Admin and Senior Managers see everything
    if user.can_view_all_tasks():
        return base_qs
    
    # Manager sees department tasks
    if user.can_view_department_tasks() and user.department:
        return base_qs.filter(
            Q(department=user.department) |
            Q(assignee=user) |
            Q(created_by=user)
        ).distinct()
    
    # Employee sees only their own tasks
    return base_qs.filter(
        Q(assignee=user) | Q(created_by=user)
    ).distinct()


def can_view_task(user, task):
    """
    Check if user can view a specific task.
    
    Rules:
    - Admin: Can view all tasks
    - Senior Manager 1/2: Can view all tasks
    - Manager: Can view tasks in their department + their own tasks
    - Employee: Can view tasks assigned to them or created by them
    """
    if not user.is_authenticated:
        return False
    
    # Admin and Senior Managers can view all
    if user.role in ['admin', 'senior_manager_1', 'senior_manager_2']:
        return True
    
    # Manager can view department tasks + own tasks
    if user.role == 'manager':
        if task.department_id == user.department_id:
            return True
        if task.assignee_id == user.pk or task.created_by_id == user.pk:
            return True
        return False
    
    # Employee can view their own tasks
    if task.assignee_id == user.pk or task.created_by_id == user.pk:
        return True
    
    return False


def get_viewable_tasks(user):
    """
    Get queryset of tasks the user can view.
    
    Returns Task queryset filtered by user's role.
    """
    if not user.is_authenticated:
        return Task.objects.none()
    
    queryset = Task.objects.select_related(
        'assignee', 'created_by', 'department'
    )
    
    # Admin and Senior Managers see all
    if user.role in ['admin', 'senior_manager_1', 'senior_manager_2']:
        return queryset
    
    # Manager sees department tasks + own tasks
    if user.role == 'manager':
        if user.department:
            return queryset.filter(
                Q(department=user.department) |
                Q(assignee=user) |
                Q(created_by=user)
            ).distinct()
        else:
            return queryset.filter(
                Q(assignee=user) | Q(created_by=user)
            ).distinct()
    
    # Employee sees own tasks only
    return queryset.filter(
        Q(assignee=user) | Q(created_by=user)
    ).distinct()


# =============================================================================
# Edit Permissions
# =============================================================================

def can_edit_task(user, task):
    """
    Check if user can edit a task.
    
    Rules:
    - Only task creator can edit
    - Admin can edit any task
    - Cannot edit cancelled or verified tasks
    """
    if not user.is_authenticated:
        return False
    
    # Cannot edit terminal states
    if task.status in ['cancelled', 'verified']:
        return False
    
    # Admin can edit any task
    if user.role == 'admin':
        return True
    
    # Only creator can edit
    return task.created_by_id == user.pk


def can_change_status(user, task):
    """
    Check if user can change task status.
    
    Rules:
    - Assignee can progress their task (pending -> in_progress -> completed)
    - Creator can verify delegated tasks
    - Admin can change any status
    - Cannot change cancelled or verified tasks
    """
    if not user.is_authenticated:
        return False
    
    # Cannot change terminal states
    if task.status in ['cancelled', 'verified']:
        return False
    
    # For completed delegated tasks, only creator/admin can verify
    if task.status == 'completed' and task.task_type == 'delegated':
        return user.pk == task.created_by_id or user.role == 'admin'
    
    # Admin can always change status
    if user.role == 'admin':
        return True
    
    # Assignee can progress their task
    if task.assignee_id == user.pk:
        return True
    
    # Creator can also change status of delegated tasks
    if task.created_by_id == user.pk and task.task_type == 'delegated':
        return True
    
    return False


def can_reassign_task(user, task):
    """
    Check if user can reassign a task.
    
    Rules:
    - Only task creator can reassign
    - Admin can reassign any task
    - Cannot reassign cancelled or verified tasks
    - Cannot reassign personal tasks (they would become delegated)
    """
    if not user.is_authenticated:
        return False
    
    # Cannot reassign terminal states
    if task.status in ['cancelled', 'verified']:
        return False
    
    # Cannot reassign personal tasks
    if task.task_type == 'personal':
        return False
    
    # Admin can reassign any task
    if user.role == 'admin':
        return True
    
    # Only creator can reassign
    return task.created_by_id == user.pk


def can_cancel_task(user, task):
    """
    Check if user can cancel a task.
    
    Rules:
    - Personal tasks: owner can cancel
    - Delegated tasks: creator or admin can cancel
    - Cannot cancel completed, verified, or already cancelled tasks
    """
    if not user.is_authenticated:
        return False
    
    # Cannot cancel terminal states
    if task.status in ['cancelled', 'verified', 'completed']:
        return False
    
    # Admin can cancel any task
    if user.role == 'admin':
        return True
    
    # Personal task - owner can cancel
    if task.task_type == 'personal':
        return task.assignee_id == user.pk
    
    # Delegated task - creator can cancel
    return task.created_by_id == user.pk


# =============================================================================
# Assignment Permissions
# =============================================================================

def can_assign_to(user, target_user):
    """
    Check if user can assign tasks to target_user.
    
    Rules:
    - Employee: Can only assign to themselves (personal tasks)
    - Manager: Can assign to themselves and users in their department
    - Senior Manager 1/2: Can assign to anyone
    - Admin: Can assign to anyone
    """
    if not user.is_authenticated:
        return False
    
    # Everyone can assign to themselves
    if user.pk == target_user.pk:
        return True
    
    # Employee can only assign to self
    if user.role == 'employee':
        return False
    
    # Admin and Senior Managers can assign to anyone
    if user.role in ['admin', 'senior_manager_1', 'senior_manager_2']:
        return True
    
    # Manager can assign within department
    if user.role == 'manager':
        return (
            user.department_id is not None and 
            user.department_id == target_user.department_id
        )
    
    return False


def get_assignable_users(user):
    """
    Get queryset of users the current user can assign tasks to.
    
    Returns User queryset based on role.
    """
    from apps.accounts.models import User as UserModel
    
    if not user.is_authenticated:
        return UserModel.objects.none()
    
    base_qs = UserModel.objects.filter(is_active=True)
    
    # Employee can only assign to self
    if user.role == 'employee':
        return base_qs.filter(pk=user.pk)
    
    # Admin and Senior Managers can assign to anyone
    if user.role in ['admin', 'senior_manager_1', 'senior_manager_2']:
        return base_qs.order_by('first_name', 'last_name')
    
    # Manager can assign within department
    if user.role == 'manager':
        if user.department:
            return base_qs.filter(department=user.department).order_by('first_name', 'last_name')
        return base_qs.filter(pk=user.pk)
    
    # Default: self only
    return base_qs.filter(pk=user.pk)


# =============================================================================
# Comment & Attachment Permissions
# =============================================================================

def can_add_comment(user, task):
    """
    Check if user can add a comment to a task.
    
    Rules:
    - Anyone who can view the task can comment
    - Cannot comment on cancelled tasks
    """
    if task.status == 'cancelled':
        return False
    return can_view_task(user, task)


def can_add_attachment(user, task):
    """
    Check if user can add/replace attachment on a task.
    
    Rules:
    - Anyone who can view the task can add attachment
    - Cannot add to cancelled or verified tasks
    """
    if task.status in ['cancelled', 'verified']:
        return False
    return can_view_task(user, task)


def can_remove_attachment(user, task):
    """
    Check if user can remove attachment from a task.
    
    Rules:
    - Task creator or admin can remove
    - Attachment uploader can remove
    """
    if task.status in ['cancelled', 'verified']:
        return False
    
    if user.role == 'admin':
        return True
    
    if task.created_by_id == user.pk:
        return True
    
    try:
        if task.attachment.uploaded_by_id == user.pk:
            return True
    except:
        pass
    
    return False
