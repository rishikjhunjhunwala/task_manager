"""
Permission helpers for tasks app.

Centralized permission checking functions for task operations.
These are used by views and services to enforce role-based access control.
"""

from django.core.exceptions import PermissionDenied


def can_assign_to_user(creator, assignee):
    """
    Check if creator can assign a task to the given assignee.
    
    Assignment Rules:
    - Employee: Can only assign to self
    - Manager: Can assign to self + users in their department
    - Senior Manager 1/2, Admin: Can assign to anyone
    
    Args:
        creator: User creating/assigning the task
        assignee: User being assigned the task
    
    Returns:
        bool: True if assignment is allowed
    """
    # Self-assignment is always allowed
    if creator == assignee:
        return True
    
    # Employees can only assign to themselves
    if creator.role == 'employee':
        return False
    
    # Managers can only assign within their department
    if creator.role == 'manager':
        if creator.department is None or assignee.department is None:
            return False
        return creator.department_id == assignee.department_id
    
    # Admin and Senior Managers can assign to anyone
    if creator.role in ['admin', 'senior_manager_1', 'senior_manager_2']:
        return True
    
    return False


def get_assignable_users(user):
    """
    Get queryset of users that the given user can assign tasks to.
    
    Args:
        user: The user who wants to assign a task
    
    Returns:
        QuerySet of User objects
    """
    from apps.accounts.models import User
    
    # Start with active users only
    base_qs = User.objects.filter(is_active=True)
    
    if user.role == 'employee':
        # Employees can only assign to themselves
        return base_qs.filter(pk=user.pk)
    
    elif user.role == 'manager':
        # Managers can assign within their department + self
        if user.department:
            return base_qs.filter(department=user.department)
        else:
            return base_qs.filter(pk=user.pk)
    
    else:
        # Admin and Senior Managers can assign to anyone
        return base_qs.order_by('first_name', 'last_name')


def can_view_task(user, task):
    """
    Check if user can view a specific task.
    
    View Rules:
    - Admin, SM1, SM2: Can view all tasks
    - Manager: Can view department tasks + own tasks
    - Employee: Can view only their own tasks (assigned or created)
    
    Args:
        user: User attempting to view
        task: Task being viewed
    
    Returns:
        bool: True if user can view the task
    """
    # Admin and Senior Managers can view everything
    if user.role in ['admin', 'senior_manager_1', 'senior_manager_2']:
        return True
    
    # User is the assignee or creator
    if task.assignee_id == user.pk or task.created_by_id == user.pk:
        return True
    
    # Manager can view department tasks
    if user.role == 'manager' and user.department:
        if task.department_id == user.department_id:
            return True
    
    return False


def can_edit_task(user, task):
    """
    Check if user can edit a specific task.
    
    Edit Rules:
    - Only the task creator can edit the task
    - Admin can also edit any task
    - Task must not be in terminal state (verified, cancelled)
    
    Args:
        user: User attempting to edit
        task: Task being edited
    
    Returns:
        bool: True if user can edit the task
    """
    # Cannot edit terminal states
    if task.status in ['verified', 'cancelled']:
        return False
    
    # Personal tasks that are completed are terminal
    if task.is_personal and task.status == 'completed':
        return False
    
    # Creator can always edit their own tasks
    if task.created_by_id == user.pk:
        return True
    
    # Admin can edit any task
    if user.role == 'admin':
        return True
    
    return False


def can_change_status(user, task):
    """
    Check if user can change the status of a task.
    
    Status Change Rules:
    - Assignee can change: pending → in_progress → completed
    - Creator can change: completed → verified (for delegated tasks)
    - Creator or Admin can cancel
    
    Args:
        user: User attempting to change status
        task: Task being modified
    
    Returns:
        bool: True if user can change status
    """
    # Cannot change terminal states
    if task.status in ['verified', 'cancelled']:
        return False
    
    # Personal completed tasks are terminal
    if task.is_personal and task.status == 'completed':
        return False
    
    # Assignee can update status (except verification)
    if task.assignee_id == user.pk:
        return True
    
    # Creator can verify delegated tasks
    if task.created_by_id == user.pk and task.status == 'completed' and task.is_delegated:
        return True
    
    # Creator can cancel
    if task.created_by_id == user.pk:
        return True
    
    # Admin can do anything
    if user.role == 'admin':
        return True
    
    return False


def can_reassign_task(user, task):
    """
    Check if user can reassign a task.
    
    Reassignment Rules:
    - Only creator can reassign
    - Admin can reassign any task
    - Cannot reassign cancelled or verified tasks
    
    Args:
        user: User attempting to reassign
        task: Task being reassigned
    
    Returns:
        bool: True if user can reassign the task
    """
    # Cannot reassign terminal states
    if task.status in ['verified', 'cancelled']:
        return False
    
    # Personal completed tasks are terminal
    if task.is_personal and task.status == 'completed':
        return False
    
    # Creator can reassign
    if task.created_by_id == user.pk:
        return True
    
    # Admin can reassign
    if user.role == 'admin':
        return True
    
    return False


def can_cancel_task(user, task):
    """
    Check if user can cancel a task.
    
    Cancellation Rules:
    - Creator can cancel their delegated tasks
    - Owner can cancel their personal tasks
    - Admin can cancel any task
    - Cannot cancel already cancelled or verified tasks
    
    Args:
        user: User attempting to cancel
        task: Task being cancelled
    
    Returns:
        bool: True if user can cancel the task
    """
    # Cannot cancel terminal states
    if task.status in ['verified', 'cancelled']:
        return False
    
    # Creator can cancel delegated tasks
    if task.created_by_id == user.pk:
        return True
    
    # Assignee can cancel personal tasks
    if task.is_personal and task.assignee_id == user.pk:
        return True
    
    # Admin can cancel any task
    if user.role == 'admin':
        return True
    
    return False


def can_add_comment(user, task):
    """
    Check if user can add a comment to a task.
    
    Comment Rules:
    - Anyone who can view the task can comment
    - Cannot comment on cancelled tasks
    
    Args:
        user: User attempting to comment
        task: Task being commented on
    
    Returns:
        bool: True if user can add a comment
    """
    if task.status == 'cancelled':
        return False
    
    return can_view_task(user, task)


def can_add_attachment(user, task):
    """
    Check if user can add/replace an attachment.
    
    Attachment Rules:
    - Creator or assignee can add attachment
    - Admin can add attachment
    - Cannot modify cancelled or verified tasks
    
    Args:
        user: User attempting to add attachment
        task: Task being modified
    
    Returns:
        bool: True if user can add attachment
    """
    # Cannot modify terminal states
    if task.status in ['verified', 'cancelled']:
        return False
    
    # Personal completed tasks are terminal
    if task.is_personal and task.status == 'completed':
        return False
    
    # Creator or assignee
    if task.created_by_id == user.pk or task.assignee_id == user.pk:
        return True
    
    # Admin
    if user.role == 'admin':
        return True
    
    return False


def require_task_permission(permission_func, user, task, message=None):
    """
    Decorator helper to raise PermissionDenied if check fails.
    
    Args:
        permission_func: One of the can_* functions
        user: User to check
        task: Task to check against
        message: Optional custom error message
    
    Raises:
        PermissionDenied: If permission check fails
    """
    if not permission_func(user, task):
        raise PermissionDenied(message or "You don't have permission to perform this action.")
