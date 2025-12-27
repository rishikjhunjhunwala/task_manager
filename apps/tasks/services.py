"""
Service layer for tasks app.

All business logic for task operations is centralized here.
This enables reuse from views (manual) and email parser (Phase 2).

Services:
- create_task: Create new task with permissions check
- update_task: Update task fields with activity logging
- change_status: Change task status with workflow validation
- reassign_task: Reassign task to different user
- cancel_task: Cancel a task with reason
- add_comment: Add comment to task
- add_or_replace_attachment: Handle task attachments
"""

from django.utils import timezone
from django.db import transaction
from django.core.exceptions import PermissionDenied, ValidationError

from .models import Task, Comment, Attachment
from .permissions import (
    can_assign_to_user, can_edit_task, can_change_status,
    can_reassign_task, can_cancel_task, can_add_comment, can_add_attachment
)
from apps.activity_log.models import log_task_activity, TaskActivity


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
        title: Task title (required)
        assignee: User to assign task to (required)
        created_by: User creating the task (required)
        description: Task description (optional)
        deadline: DateTime when task is due (optional)
        priority: low/medium/high/critical (default: medium)
        source: manual/email (default: manual)
        source_reference: Email ID for Phase 2 (optional)
    
    Returns:
        Created Task instance
    
    Raises:
        PermissionDenied: If assignment violates role-based rules
        ValidationError: If required fields are missing
    """
    # Validate required fields
    if not title or not title.strip():
        raise ValidationError("Task title is required.")
    
    if not assignee:
        raise ValidationError("Assignee is required.")
    
    if not created_by:
        raise ValidationError("Creator is required.")
    
    # Check if assignee is active
    if not assignee.is_active:
        raise ValidationError("Cannot assign task to inactive user.")
    
    # Validate assignment permissions
    if not can_assign_to_user(created_by, assignee):
        if created_by.role == 'employee':
            raise PermissionDenied("Employees can only create personal tasks.")
        elif created_by.role == 'manager':
            raise PermissionDenied("Managers can only assign tasks within their department.")
        else:
            raise PermissionDenied("You don't have permission to assign tasks to this user.")
    
    # Validate priority
    valid_priorities = ['low', 'medium', 'high', 'critical']
    if priority not in valid_priorities:
        priority = 'medium'
    
    # Validate deadline is in the future (if provided)
    if deadline and deadline < timezone.now():
        raise ValidationError("Deadline cannot be in the past.")
    
    # Check if assignee has a department
    if not assignee.department:
        raise ValidationError(f"User {assignee.get_full_name()} is not assigned to any department.")
    
    with transaction.atomic():
        # Create the task
        # Note: reference_number, task_type, and department are auto-set in model.save()
        task = Task.objects.create(
            title=title.strip(),
            description=description.strip() if description else '',
            assignee=assignee,
            created_by=created_by,
            department=assignee.department,
            deadline=deadline,
            priority=priority,
            source=source,
            source_reference=source_reference
        )
        
        # Log activity
        if task.is_personal:
            description_text = f'Personal task created: "{task.title}"'
        else:
            description_text = f'Task created and assigned to {assignee.get_full_name()}'
        
        log_task_activity(
            task=task,
            user=created_by,
            action_type=TaskActivity.ActionType.CREATED,
            description=description_text
        )
        
        # Send notification for delegated tasks (will be implemented in Phase 9)
        if task.is_delegated:
            _notify_task_assigned(task)
    
    return task


def update_task(task, user, **kwargs):
    """
    Update task fields with activity logging.
    Only task creator (or admin) can edit.
    
    Args:
        task: Task instance to update
        user: User performing the update
        **kwargs: Fields to update (title, description, priority, deadline)
    
    Returns:
        Updated Task instance
    
    Raises:
        PermissionDenied: If user cannot edit the task
        ValidationError: If validation fails
    """
    if not can_edit_task(user, task):
        raise PermissionDenied("You don't have permission to edit this task.")
    
    # Editable fields
    editable_fields = ['title', 'description', 'priority', 'deadline']
    changes = []
    
    with transaction.atomic():
        for field in editable_fields:
            if field in kwargs:
                new_value = kwargs[field]
                old_value = getattr(task, field)
                
                # Process field-specific validation
                if field == 'title':
                    if not new_value or not new_value.strip():
                        raise ValidationError("Task title cannot be empty.")
                    new_value = new_value.strip()
                
                elif field == 'description':
                    new_value = new_value.strip() if new_value else ''
                
                elif field == 'priority':
                    valid_priorities = ['low', 'medium', 'high', 'critical']
                    if new_value not in valid_priorities:
                        raise ValidationError(f"Invalid priority: {new_value}")
                
                elif field == 'deadline':
                    # Allow clearing deadline (None) or future dates
                    if new_value and new_value < timezone.now():
                        raise ValidationError("Deadline cannot be in the past.")
                
                # Check if value actually changed
                if old_value != new_value:
                    # Format values for logging
                    if field == 'deadline':
                        old_display = old_value.strftime('%d %b %Y, %I:%M %p') if old_value else 'None'
                        new_display = new_value.strftime('%d %b %Y, %I:%M %p') if new_value else 'None'
                    elif field == 'priority':
                        old_display = old_value.capitalize() if old_value else 'None'
                        new_display = new_value.capitalize() if new_value else 'None'
                    else:
                        old_display = str(old_value) if old_value else 'None'
                        new_display = str(new_value) if new_value else 'None'
                    
                    changes.append({
                        'field': field,
                        'old_value': old_display,
                        'new_value': new_display
                    })
                    
                    setattr(task, field, new_value)
        
        if changes:
            task.save()
            
            # Log each change
            for change in changes:
                log_task_activity(
                    task=task,
                    user=user,
                    action_type=TaskActivity.ActionType.UPDATED,
                    description=f'{change["field"].replace("_", " ").title()} changed from "{change["old_value"]}" to "{change["new_value"]}"',
                    field_name=change['field'],
                    old_value=change['old_value'],
                    new_value=change['new_value']
                )
    
    return task


def change_status(task, user, new_status):
    """
    Change task status with workflow validation.
    
    Workflow Rules:
    - Delegated: pending → in_progress → completed → verified
    - Personal: pending → in_progress → completed (terminal)
    - Any status can go to cancelled (with permission)
    
    Args:
        task: Task instance
        user: User changing the status
        new_status: Target status
    
    Returns:
        Updated Task instance
    
    Raises:
        PermissionDenied: If user cannot change status
        ValidationError: If transition is invalid
    """
    if not can_change_status(user, task):
        raise PermissionDenied("You don't have permission to change this task's status.")
    
    old_status = task.status
    
    # Validate transition
    if new_status == 'cancelled':
        # Cancellation is handled by cancel_task()
        raise ValidationError("Use cancel_task() to cancel tasks.")
    
    if not task.can_transition_to(new_status):
        raise ValidationError(
            f"Cannot change status from '{task.get_status_display()}' to "
            f"'{dict(Task.Status.choices).get(new_status, new_status)}'."
        )
    
    # Additional permission checks for specific transitions
    if new_status == 'verified':
        # Only creator can verify delegated tasks
        if task.created_by_id != user.pk and user.role != 'admin':
            raise PermissionDenied("Only the task creator can verify this task.")
    
    if new_status in ['in_progress', 'completed']:
        # Only assignee can mark as in_progress or completed
        if task.assignee_id != user.pk and user.role != 'admin':
            raise PermissionDenied("Only the assignee can update this task's status.")
    
    with transaction.atomic():
        task.status = new_status
        
        # Set completion timestamp
        if new_status == 'completed':
            task.completed_at = timezone.now()
        
        task.save()
        
        # Log activity
        log_task_activity(
            task=task,
            user=user,
            action_type=TaskActivity.ActionType.STATUS_CHANGED,
            description=f'Status changed from {dict(Task.Status.choices).get(old_status)} to {dict(Task.Status.choices).get(new_status)}',
            field_name='status',
            old_value=old_status,
            new_value=new_status
        )
        
        # Send notifications based on status change
        if new_status == 'completed' and task.is_delegated:
            # Notify creator that task is completed (Phase 9)
            _notify_task_completed(task)
        
        elif new_status == 'verified':
            # Notify assignee that task is verified (Phase 9)
            _notify_task_verified(task)
    
    return task


def reassign_task(task, user, new_assignee):
    """
    Reassign task to a new user.
    Only task creator (or admin) can reassign.
    Old assignee is NOT notified. Overdue clock does NOT reset.
    
    Args:
        task: Task instance
        user: User performing the reassignment
        new_assignee: New assignee User
    
    Returns:
        Updated Task instance
    
    Raises:
        PermissionDenied: If user cannot reassign
        ValidationError: If assignment is invalid
    """
    if not can_reassign_task(user, task):
        raise PermissionDenied("You don't have permission to reassign this task.")
    
    # Check if new assignee is active
    if not new_assignee.is_active:
        raise ValidationError("Cannot reassign task to inactive user.")
    
    # Check if new assignee has a department
    if not new_assignee.department:
        raise ValidationError(f"User {new_assignee.get_full_name()} is not assigned to any department.")
    
    # Validate assignment permissions
    if not can_assign_to_user(user, new_assignee):
        raise PermissionDenied("You don't have permission to assign tasks to this user.")
    
    # Check if reassigning to same user
    if task.assignee_id == new_assignee.pk:
        raise ValidationError("Task is already assigned to this user.")
    
    old_assignee = task.assignee
    
    with transaction.atomic():
        task.assignee = new_assignee
        task.department = new_assignee.department
        
        # Update task_type if needed
        if new_assignee.pk == task.created_by_id:
            task.task_type = Task.TaskType.PERSONAL
        else:
            task.task_type = Task.TaskType.DELEGATED
        
        task.save()
        
        # Log activity
        log_task_activity(
            task=task,
            user=user,
            action_type=TaskActivity.ActionType.REASSIGNED,
            description=f'Reassigned from {old_assignee.get_full_name()} to {new_assignee.get_full_name()}',
            field_name='assignee',
            old_value=old_assignee.email,
            new_value=new_assignee.email
        )
        
        # Notify new assignee only (old assignee NOT notified)
        _notify_task_assigned(task)
    
    return task


def cancel_task(task, user, reason=None):
    """
    Cancel a task.
    
    Args:
        task: Task instance
        user: User cancelling the task
        reason: Optional cancellation reason
    
    Returns:
        Updated Task instance
    
    Raises:
        PermissionDenied: If user cannot cancel
    """
    if not can_cancel_task(user, task):
        raise PermissionDenied("You don't have permission to cancel this task.")
    
    old_status = task.status
    
    with transaction.atomic():
        task.status = Task.Status.CANCELLED
        task.cancelled_at = timezone.now()
        task.cancelled_by = user
        task.save()
        
        # Log activity
        description = 'Task cancelled'
        if reason:
            description += f': {reason}'
        
        log_task_activity(
            task=task,
            user=user,
            action_type=TaskActivity.ActionType.CANCELLED,
            description=description,
            field_name='status',
            old_value=old_status,
            new_value='cancelled'
        )
        
        # Notify assignee (Phase 9)
        if task.assignee_id != user.pk:
            _notify_task_cancelled(task, reason)
    
    return task


def add_comment(task, user, content):
    """
    Add a comment to a task.
    
    Args:
        task: Task instance
        user: User adding the comment
        content: Comment content
    
    Returns:
        Created Comment instance
    
    Raises:
        PermissionDenied: If user cannot comment
        ValidationError: If content is empty
    """
    if not can_add_comment(user, task):
        raise PermissionDenied("You cannot add comments to this task.")
    
    if not content or not content.strip():
        raise ValidationError("Comment cannot be empty.")
    
    with transaction.atomic():
        comment = Comment.objects.create(
            task=task,
            author=user,
            content=content.strip()
        )
        
        # Log activity
        log_task_activity(
            task=task,
            user=user,
            action_type=TaskActivity.ActionType.COMMENTED,
            description=f'Comment added: "{content[:50]}{"..." if len(content) > 50 else ""}"'
        )
    
    return comment


def add_or_replace_attachment(task, user, file):
    """
    Add or replace task attachment.
    Each task can have only one attachment.
    
    Args:
        task: Task instance
        user: User uploading the file
        file: UploadedFile instance
    
    Returns:
        Created/Updated Attachment instance
    
    Raises:
        PermissionDenied: If user cannot add attachment
        ValidationError: If file validation fails
    """
    if not can_add_attachment(user, task):
        raise PermissionDenied("You don't have permission to add attachments to this task.")
    
    # Validate file size (2 MB max)
    max_size = Attachment.MAX_SIZE_BYTES
    if file.size > max_size:
        raise ValidationError(f"File size cannot exceed {Attachment.MAX_SIZE_MB} MB.")
    
    # Validate file extension
    import os
    ext = os.path.splitext(file.name)[1].lower().lstrip('.')
    if ext not in Attachment.ALLOWED_EXTENSIONS:
        allowed = ', '.join(Attachment.ALLOWED_EXTENSIONS).upper()
        raise ValidationError(f"File type not allowed. Allowed types: {allowed}")
    
    with transaction.atomic():
        # Check for existing attachment
        existing = None
        try:
            existing = task.attachment
        except Attachment.DoesNotExist:
            pass
        
        if existing:
            # Replace existing attachment
            old_filename = existing.filename
            existing.delete()  # This also deletes the file from storage
            
            action_type = TaskActivity.ActionType.ATTACHMENT_REPLACED
            description = f'Attachment replaced: "{old_filename}" → "{file.name}"'
        else:
            action_type = TaskActivity.ActionType.ATTACHMENT_ADDED
            description = f'Attachment added: "{file.name}"'
        
        # Create new attachment
        attachment = Attachment.objects.create(
            task=task,
            uploaded_by=user,
            file=file,
            filename=file.name,
            file_size=file.size
        )
        
        # Log activity
        log_task_activity(
            task=task,
            user=user,
            action_type=action_type,
            description=description
        )
    
    return attachment


def delete_attachment(task, user):
    """
    Delete task attachment.
    
    Args:
        task: Task instance
        user: User deleting the attachment
    
    Returns:
        bool: True if attachment was deleted
    
    Raises:
        PermissionDenied: If user cannot delete attachment
        ValidationError: If no attachment exists
    """
    if not can_add_attachment(user, task):
        raise PermissionDenied("You don't have permission to delete attachments from this task.")
    
    try:
        attachment = task.attachment
    except Attachment.DoesNotExist:
        raise ValidationError("This task has no attachment.")
    
    filename = attachment.filename
    
    with transaction.atomic():
        attachment.delete()
        
        # Log activity
        log_task_activity(
            task=task,
            user=user,
            action_type=TaskActivity.ActionType.ATTACHMENT_REPLACED,
            description=f'Attachment removed: "{filename}"'
        )
    
    return True


# =============================================================================
# Notification Stubs (Will be implemented in Phase 9)
# =============================================================================

def _notify_task_assigned(task):
    """
    Send notification when a task is assigned.
    Only for delegated tasks (assignee != creator).
    
    Will be implemented in Phase 9.
    """
    # TODO: Implement in Phase 9
    # from apps.notifications.services import notify_task_assigned
    # notify_task_assigned(task)
    pass


def _notify_task_completed(task):
    """
    Send notification to creator when a delegated task is completed.
    
    Will be implemented in Phase 9.
    """
    # TODO: Implement in Phase 9
    pass


def _notify_task_verified(task):
    """
    Send notification to assignee when task is verified.
    
    Will be implemented in Phase 9.
    """
    # TODO: Implement in Phase 9
    pass


def _notify_task_cancelled(task, reason=None):
    """
    Send notification to assignee when task is cancelled.
    
    Will be implemented in Phase 9.
    """
    # TODO: Implement in Phase 9
    pass


# =============================================================================
# Query Helpers
# =============================================================================

def get_tasks_for_user(user, tab='assigned_to_me'):
    """
    Get filtered task queryset based on user role and selected tab.
    
    Args:
        user: Current user
        tab: One of 'my_personal', 'assigned_to_me', 'i_assigned'
    
    Returns:
        QuerySet of Task objects
    """
    base_qs = Task.objects.select_related(
        'assignee', 'created_by', 'department'
    ).prefetch_related('comments')
    
    if tab == 'my_personal':
        # Personal tasks: created by me AND assigned to me
        return base_qs.filter(
            created_by=user,
            assignee=user,
            task_type=Task.TaskType.PERSONAL
        ).exclude(status='cancelled')
    
    elif tab == 'assigned_to_me':
        # Delegated tasks assigned to me (NOT my personal tasks)
        return base_qs.filter(
            assignee=user,
            task_type=Task.TaskType.DELEGATED
        ).exclude(status='cancelled')
    
    elif tab == 'i_assigned':
        # Tasks I delegated to others
        return base_qs.filter(
            created_by=user,
            task_type=Task.TaskType.DELEGATED
        ).exclude(assignee=user).exclude(status='cancelled')
    
    return base_qs.none()


def get_task_counts(user):
    """
    Get task counts for dashboard badges.
    
    Args:
        user: Current user
    
    Returns:
        dict with counts for each tab
    """
    from django.db.models import Q, Count
    
    # Personal tasks (pending + in_progress)
    personal_count = Task.objects.filter(
        created_by=user,
        assignee=user,
        task_type=Task.TaskType.PERSONAL,
        status__in=['pending', 'in_progress']
    ).count()
    
    # Assigned to me (delegated, pending + in_progress)
    assigned_to_me_count = Task.objects.filter(
        assignee=user,
        task_type=Task.TaskType.DELEGATED,
        status__in=['pending', 'in_progress']
    ).count()
    
    # I assigned (delegated to others, pending + in_progress)
    i_assigned_count = Task.objects.filter(
        created_by=user,
        task_type=Task.TaskType.DELEGATED,
        status__in=['pending', 'in_progress']
    ).exclude(assignee=user).count()
    
    # Overdue tasks (assigned to me)
    overdue_count = Task.objects.filter(
        assignee=user,
        status__in=['pending', 'in_progress'],
        deadline__lt=timezone.now()
    ).exclude(deadline__isnull=True).count()
    
    return {
        'my_personal': personal_count,
        'assigned_to_me': assigned_to_me_count,
        'i_assigned': i_assigned_count,
        'overdue': overdue_count,
        'total_pending': personal_count + assigned_to_me_count,
    }
