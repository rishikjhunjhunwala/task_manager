"""
Permission functions for tasks app.

This module contains all permission-checking functions used throughout the
tasks application. Each function encapsulates specific business rules for
determining what actions users can perform.

Role Hierarchy:
- Admin: Full access to everything
- Senior Manager 1/2: Can view all tasks, manage escalations
- Manager: Can view department tasks, assign within department
- Employee: Can only see/manage their own tasks

UPDATED in Phase 7B:
- can_add_comment: Now restricts to creator/assignee/admin/SM only
- can_add_attachment: Now restricts to creator/assignee/admin/SM only
"""

from django.db.models import Q


# =============================================================================
# View Permissions
# =============================================================================

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
    from .models import Task
    
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


def get_visible_tasks(user):
    """
    Get queryset of tasks visible to this user based on their role.
    Alias for get_viewable_tasks for backwards compatibility.
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


def can_change_task_status(user, task):
    """Alias for can_change_status for backwards compatibility."""
    return can_change_status(user, task)


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
# Status Transition Logic
# =============================================================================

def get_allowed_status_transitions(user, task):
    """
    Get list of status values the user can transition to.
    
    Returns list of (value, display) tuples for form choices.
    """
    from .models import Task
    
    if not can_change_status(user, task):
        return []
    
    current = task.status
    transitions = []
    
    # Define possible transitions based on current status
    if current == 'pending':
        transitions = [('in_progress', 'In Progress')]
    elif current == 'in_progress':
        transitions = [('completed', 'Completed')]
    elif current == 'completed':
        # Only delegated tasks can be verified
        if task.task_type == 'delegated':
            transitions = [('verified', 'Verified')]
    
    # Admin can also transition back (for corrections)
    if user.role == 'admin':
        if current == 'in_progress':
            transitions.append(('pending', 'Pending'))
        elif current == 'completed':
            transitions.append(('in_progress', 'In Progress'))
    
    return transitions


# =============================================================================
# Comment & Attachment Permissions (UPDATED in Phase 7B)
# =============================================================================

def can_add_comment(user, task):
    """
    Check if user can add a comment to a task.
    
    Rules (UPDATED in Phase 7B - more restrictive):
    - Cannot comment on cancelled tasks
    - Only these users can comment:
      - Task creator
      - Task assignee
      - Admin
      - Senior Manager 1
      - Senior Manager 2
    
    NOTE: This is more restrictive than can_view_task.
    Managers and Employees who can VIEW a task but are NOT the 
    creator/assignee should NOT be able to comment.
    """
    if not user.is_authenticated:
        return False
    
    # Cannot comment on cancelled tasks
    if task.status == 'cancelled':
        return False
    
    # Admin and Senior Managers can always comment
    if user.role in ['admin', 'senior_manager_1', 'senior_manager_2']:
        return True
    
    # Task creator can comment
    if task.created_by_id == user.pk:
        return True
    
    # Task assignee can comment
    if task.assignee_id == user.pk:
        return True
    
    return False


def can_add_attachment(user, task):
    """
    Check if user can add/replace attachment on a task.
    
    Rules (UPDATED in Phase 7B - more restrictive):
    - Cannot add to cancelled or verified tasks
    - Only these users can add attachments:
      - Task creator
      - Task assignee
      - Admin
      - Senior Manager 1
      - Senior Manager 2
    
    NOTE: This is more restrictive than can_view_task.
    Managers and Employees who can VIEW a task but are NOT the 
    creator/assignee should NOT be able to add attachments.
    """
    if not user.is_authenticated:
        return False
    
    # Cannot add to terminal states
    if task.status in ['cancelled', 'verified']:
        return False
    
    # Admin and Senior Managers can always add attachments
    if user.role in ['admin', 'senior_manager_1', 'senior_manager_2']:
        return True
    
    # Task creator can add attachment
    if task.created_by_id == user.pk:
        return True
    
    # Task assignee can add attachment
    if task.assignee_id == user.pk:
        return True
    
    return False


def can_remove_attachment(user, task):
    """
    Check if user can remove attachment from a task.
    
    Rules:
    - Cannot remove from cancelled or verified tasks
    - Admin can always remove
    - Task creator can remove
    - Attachment uploader can remove their own upload
    """
    if not user.is_authenticated:
        return False
    
    # Cannot remove from terminal states
    if task.status in ['cancelled', 'verified']:
        return False
    
    # Admin can always remove
    if user.role == 'admin':
        return True
    
    # Task creator can remove
    if task.created_by_id == user.pk:
        return True
    
    # Attachment uploader can remove
    try:
        if task.attachment.uploaded_by_id == user.pk:
            return True
    except:
        pass
    
    return False