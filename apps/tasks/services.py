"""
Service layer for tasks app.

All business logic for task operations is centralized here.
This enables reuse from views (manual) and email parser (Phase 2).

Will be fully implemented in Phase 5 (Core Task Management).
"""

from django.utils import timezone
from django.db import transaction
from django.core.exceptions import PermissionError

from .models import Task, Comment, Attachment


def create_task(
    title: str,
    assignee,
    created_by,
    description: str = '',
    deadline=None,
    priority: str = 'medium',
    source: str = 'manual',
    source_reference: str = None
):
    """
    Central task creation function.
    Called by views (manual) and email parser (automated in Phase 2).
    
    Args:
        title: Task title
        assignee: User to assign task to
        created_by: User creating the task
        description: Task description
        deadline: DateTime when task is due
        priority: low/medium/high/critical
        source: manual/email
        source_reference: Email ID for Phase 2
    
    Returns:
        Created Task instance
    
    Raises:
        PermissionError: If assignment violates role-based rules
    """
    # Validate assignment permissions
    if assignee != created_by:
        if created_by.role == 'employee':
            raise PermissionError("Employees can only create personal tasks")
        if created_by.role == 'manager' and assignee.department != created_by.department:
            raise PermissionError("Managers can only assign within their department")
    
    # Determine task type
    task_type = 'personal' if assignee == created_by else 'delegated'
    
    with transaction.atomic():
        task = Task.objects.create(
            title=title,
            description=description,
            assignee=assignee,
            created_by=created_by,
            department=assignee.department,
            task_type=task_type,
            deadline=deadline,
            priority=priority,
            source=source,
            source_reference=source_reference
        )
        
        # Log activity (will be implemented in Phase 5)
        # log_task_activity(task, created_by, 'created', f'Task created and assigned to {assignee.get_full_name()}')
        
        # Notify assignee if delegated (will be implemented in Phase 9)
        # if task_type == 'delegated':
        #     notify_task_assigned(task)
    
    return task


def update_task(task, user, **kwargs):
    """
    Update task fields.
    Only task creator can edit.
    
    Will be implemented in Phase 5.
    """
    pass


def change_status(task, user, new_status):
    """
    Change task status with workflow validation.
    
    Will be implemented in Phase 5.
    """
    pass


def reassign_task(task, user, new_assignee):
    """
    Reassign task to a new user.
    Only task creator can reassign.
    
    Will be implemented in Phase 5.
    """
    pass


def cancel_task(task, user, reason=None):
    """
    Cancel a task.
    
    Will be implemented in Phase 5.
    """
    pass


def add_comment(task, user, content):
    """
    Add a comment to a task.
    
    Will be implemented in Phase 7.
    """
    pass


def add_or_replace_attachment(task, user, file):
    """
    Add or replace task attachment.
    
    Will be implemented in Phase 7.
    """
    pass
