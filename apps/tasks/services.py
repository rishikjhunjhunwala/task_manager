"""
Service layer for tasks app.

All business logic for task operations is centralized here.
This enables reuse from views (manual) and email parser (Phase 2).
"""

from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError

from .models import Task, Comment, Attachment
from apps.activity_log.models import log_task_activity


# =============================================================================
# Task Creation
# =============================================================================

def create_task(
    title,
    assignee,
    created_by,
    description='',
    deadline=None,
    priority='medium',
    source='manual',
    source_reference=None
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
    from .permissions import can_assign_to
    
    # Validate assignment permissions
    if not can_assign_to(created_by, assignee):
        if created_by.role == 'employee':
            raise PermissionError("Employees can only create personal tasks")
        elif created_by.role == 'manager':
            raise PermissionError("Managers can only assign within their department")
        else:
            raise PermissionError("You cannot assign tasks to this user")
    
    with transaction.atomic():
        task = Task.objects.create(
            title=title,
            description=description,
            assignee=assignee,
            created_by=created_by,
            department=assignee.department,
            deadline=deadline,
            priority=priority,
            source=source,
            source_reference=source_reference
        )
        
        # Log activity
        if task.task_type == 'personal':
            description_text = f'Personal task created'
        else:
            description_text = f'Task created and assigned to {assignee.get_full_name()}'
        
        log_task_activity(
            task=task,
            user=created_by,
            action_type='created',
            description=description_text
        )
        
        # Phase 9D: Notify assignee if delegated task
        if task.task_type == 'delegated':
            from apps.notifications.services import notify_task_assigned
            notify_task_assigned(task)
    
    return task


# =============================================================================
# Task Updates
# =============================================================================

def update_task(task, user, **kwargs):
    """
    Update task fields with change tracking.
    Only task creator or admin can edit.
    
    Args:
        task: Task instance to update
        user: User making the change
        **kwargs: Fields to update (title, description, priority, deadline)
    
    Returns:
        Updated Task instance
    
    Raises:
        PermissionError: If user cannot edit the task
    """
    from .permissions import can_edit_task
    
    if not can_edit_task(user, task):
        raise PermissionError("You do not have permission to edit this task")
    
    changed_fields = []
    
    with transaction.atomic():
        # Track and apply changes
        if 'title' in kwargs and kwargs['title'] != task.title:
            old_value = task.title
            task.title = kwargs['title']
            changed_fields.append(('title', old_value, kwargs['title']))
        
        if 'description' in kwargs and kwargs['description'] != task.description:
            old_value = task.description
            task.description = kwargs['description']
            changed_fields.append(('description', old_value[:100] + '...' if len(old_value) > 100 else old_value, 
                                   kwargs['description'][:100] + '...' if len(kwargs['description']) > 100 else kwargs['description']))
        
        if 'priority' in kwargs and kwargs['priority'] != task.priority:
            old_value = task.get_priority_display()
            task.priority = kwargs['priority']
            changed_fields.append(('priority', old_value, task.get_priority_display()))
        
        if 'deadline' in kwargs:
            new_deadline = kwargs['deadline']
            if (task.deadline is None and new_deadline is not None) or \
               (task.deadline is not None and new_deadline is None) or \
               (task.deadline != new_deadline):
                old_value = task.deadline.strftime('%d %b %Y, %I:%M %p') if task.deadline else 'No deadline'
                task.deadline = new_deadline
                new_display = new_deadline.strftime('%d %b %Y, %I:%M %p') if new_deadline else 'No deadline'
                changed_fields.append(('deadline', old_value, new_display))
        
        if changed_fields:
            task.save()
            
            # Log each field change
            for field_name, old_value, new_value in changed_fields:
                log_task_activity(
                    task=task,
                    user=user,
                    action_type='updated',
                    description=f'{field_name.replace("_", " ").title()} changed from "{old_value}" to "{new_value}"',
                    field_name=field_name,
                    old_value=str(old_value),
                    new_value=str(new_value)
                )
    
    return task


# =============================================================================
# Status Changes
# =============================================================================

def change_status(task, user, new_status):
    """
    Change task status with workflow validation.
    
    Workflow:
    - Delegated: pending → in_progress → completed → verified
    - Personal: pending → in_progress → completed (no verification)
    - Any status can go to cancelled
    
    Args:
        task: Task instance
        user: User making the change
        new_status: New status value
    
    Returns:
        Updated Task instance
    
    Raises:
        PermissionError: If user cannot change status
        ValidationError: If status transition is invalid
    """
    from .permissions import can_change_status
    
    if not can_change_status(user, task):
        raise PermissionError("You do not have permission to change this task's status")
    
    # Validate transition
    if not task.can_transition_to(new_status):
        raise ValidationError(
            f"Cannot transition from {task.get_status_display()} to {dict(Task.Status.choices).get(new_status)}"
        )
    
    old_status = task.status
    old_display = task.get_status_display()
    
    with transaction.atomic():
        task.status = new_status
        
        # Set timestamps for terminal states
        if new_status == 'completed':
            task.completed_at = timezone.now()
        elif new_status == 'cancelled':
            task.cancelled_at = timezone.now()
            task.cancelled_by = user
        
        task.save()
        
        # Determine action type for logging
        if new_status == 'verified':
            action_type = 'verified'
            description = f'Task verified by {user.get_full_name()}'
        elif new_status == 'cancelled':
            action_type = 'cancelled'
            description = f'Task cancelled by {user.get_full_name()}'
        else:
            action_type = 'status_changed'
            description = f'Status changed from {old_display} to {task.get_status_display()}'
        
        log_task_activity(
            task=task,
            user=user,
            action_type=action_type,
            description=description,
            field_name='status',
            old_value=old_status,
            new_value=new_status
        )
        
        # Phase 9D: Send notifications based on status change
        if new_status == 'completed' and task.task_type == 'delegated':
            from apps.notifications.services import notify_task_completed
            notify_task_completed(task)
        elif new_status == 'verified':
            from apps.notifications.services import notify_task_verified
            notify_task_verified(task)
    
    return task


# =============================================================================
# Task Reassignment
# =============================================================================

def reassign_task(task, user, new_assignee):
    """
    Reassign task to a new user.
    Only task creator or admin can reassign.
    Old assignee is NOT notified. Overdue clock does NOT reset.
    
    Args:
        task: Task instance
        user: User making the change
        new_assignee: New assignee User instance
    
    Returns:
        Updated Task instance
    
    Raises:
        PermissionError: If user cannot reassign
    """
    from .permissions import can_reassign_task, can_assign_to
    
    if not can_reassign_task(user, task):
        raise PermissionError("You do not have permission to reassign this task")
    
    if not can_assign_to(user, new_assignee):
        raise PermissionError(f"You cannot assign tasks to {new_assignee.get_full_name()}")
    
    if task.assignee_id == new_assignee.pk:
        raise ValidationError("Task is already assigned to this user")
    
    old_assignee = task.assignee
    
    with transaction.atomic():
        task.assignee = new_assignee
        task.department = new_assignee.department
        # Note: task_type stays 'delegated' since it was already assigned to someone else
        task.save()
        
        log_task_activity(
            task=task,
            user=user,
            action_type='reassigned',
            description=f'Reassigned from {old_assignee.get_full_name()} to {new_assignee.get_full_name()}',
            field_name='assignee',
            old_value=old_assignee.email,
            new_value=new_assignee.email
        )
        
        # Phase 9D: Notify NEW assignee only (old assignee is NOT notified per requirements)
        from apps.notifications.services import notify_task_reassigned
        notify_task_reassigned(task, new_assignee, user)
    
    return task


# =============================================================================
# Task Cancellation
# =============================================================================

def cancel_task(task, user, reason=None):
    """
    Cancel a task.
    
    Args:
        task: Task instance
        user: User making the change
        reason: Optional cancellation reason
    
    Returns:
        Updated Task instance
    
    Raises:
        PermissionError: If user cannot cancel
    """
    from .permissions import can_cancel_task
    
    if not can_cancel_task(user, task):
        raise PermissionError("You do not have permission to cancel this task")
    
    with transaction.atomic():
        task.status = 'cancelled'
        task.cancelled_at = timezone.now()
        task.cancelled_by = user
        task.save()
        
        description = f'Task cancelled by {user.get_full_name()}'
        if reason:
            description += f'. Reason: {reason}'
        
        log_task_activity(
            task=task,
            user=user,
            action_type='cancelled',
            description=description
        )
        
        # Phase 9D: Notify assignee of cancellation (for delegated tasks)
        if task.task_type == 'delegated' and task.assignee_id != user.pk:
            from apps.notifications.services import notify_task_cancelled
            notify_task_cancelled(task, reason or 'No reason provided', user)
    
    return task


# =============================================================================
# Comments
# =============================================================================

def add_comment(task, user, content):
    """
    Add a comment to a task.
    
    Args:
        task: Task instance
        user: User adding the comment
        content: Comment text
    
    Returns:
        Created Comment instance
    """
    from .permissions import can_add_comment
    
    if not can_add_comment(user, task):
        raise PermissionError("You cannot add comments to this task")
    
    if not content or not content.strip():
        raise ValidationError("Comment cannot be empty")
    
    with transaction.atomic():
        comment = Comment.objects.create(
            task=task,
            author=user,
            content=content.strip()
        )
        
        log_task_activity(
            task=task,
            user=user,
            action_type='commented',
            description=f'Comment added: "{content[:50]}{"..." if len(content) > 50 else ""}"'
        )
    
    return comment


# =============================================================================
# Attachments
# =============================================================================

def add_or_replace_attachment(task, user, file):
    """
    Add or replace task attachment.
    
    Args:
        task: Task instance
        user: User uploading the file
        file: Uploaded file object
    
    Returns:
        Created/Updated Attachment instance
    
    Raises:
        ValidationError: If file is invalid
    """
    from .permissions import can_add_attachment
    
    if not can_add_attachment(user, task):
        raise PermissionError("You cannot add attachments to this task")
    
    # Validate file size
    if file.size > Attachment.MAX_SIZE_BYTES:
        raise ValidationError(f"File size cannot exceed {Attachment.MAX_SIZE_MB} MB")
    
    # Validate file extension
    import os
    ext = os.path.splitext(file.name)[1].lower().lstrip('.')
    if ext not in Attachment.ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"File type not allowed. Allowed types: {', '.join(Attachment.ALLOWED_EXTENSIONS)}"
        )
    
    with transaction.atomic():
        # Check if attachment already exists
        try:
            existing = task.attachment
            # Delete old file
            if existing.file:
                existing.file.delete(save=False)
            existing.delete()
            action_type = 'attachment_replaced'
            description = f'Attachment replaced: {file.name}'
        except Attachment.DoesNotExist:
            action_type = 'attachment_added'
            description = f'Attachment added: {file.name}'
        
        # Create new attachment
        attachment = Attachment.objects.create(
            task=task,
            uploaded_by=user,
            file=file,
            filename=file.name,
            file_size=file.size
        )
        
        log_task_activity(
            task=task,
            user=user,
            action_type=action_type,
            description=description
        )
    
    return attachment


def remove_attachment(task, user):
    """
    Remove task attachment.
    
    Args:
        task: Task instance
        user: User removing the attachment
    """
    from .permissions import can_remove_attachment
    
    if not can_remove_attachment(user, task):
        raise PermissionError("You cannot remove this attachment")
    
    try:
        attachment = task.attachment
        filename = attachment.filename
        
        with transaction.atomic():
            # Delete file from storage
            if attachment.file:
                attachment.file.delete(save=False)
            attachment.delete()
            
            log_task_activity(
                task=task,
                user=user,
                action_type='updated',
                description=f'Attachment removed: {filename}'
            )
    except Attachment.DoesNotExist:
        raise ValidationError("No attachment to remove")
