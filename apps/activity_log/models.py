"""
Activity log model for task audit trails.

Logs all task changes including:
- Task creation
- Field updates (with old/new values)
- Status changes
- Reassignments
- Comments added
- Attachments uploaded/replaced
- Task cancellation
- Task verification
"""

from django.db import models
from django.conf import settings


class TaskActivity(models.Model):
    """
    Audit log for task activities.
    
    Access: Admin only
    Retention: 5 years
    """

    class ActionType(models.TextChoices):
        CREATED = 'created', 'Created'
        UPDATED = 'updated', 'Updated'
        STATUS_CHANGED = 'status_changed', 'Status Changed'
        REASSIGNED = 'reassigned', 'Reassigned'
        COMMENTED = 'commented', 'Commented'
        ATTACHMENT_ADDED = 'attachment_added', 'Attachment Added'
        ATTACHMENT_REPLACED = 'attachment_replaced', 'Attachment Replaced'
        CANCELLED = 'cancelled', 'Cancelled'
        VERIFIED = 'verified', 'Verified'

    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.CASCADE,
        related_name='activities',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='task_activities',
        help_text='User who performed the action'
    )
    action_type = models.CharField(
        max_length=20,
        choices=ActionType.choices,
        db_index=True,
    )
    description = models.TextField(
        help_text='Human-readable description of the change'
    )
    
    # For field-level changes
    field_name = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text='Name of the field that was changed'
    )
    old_value = models.TextField(
        null=True,
        blank=True,
        help_text='Previous value (for field changes)'
    )
    new_value = models.TextField(
        null=True,
        blank=True,
        help_text='New value (for field changes)'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'task activity'
        verbose_name_plural = 'task activities'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action_type', '-created_at']),
        ]

    def __str__(self):
        return f"{self.task.reference_number} - {self.get_action_type_display()} by {self.user}"


def log_task_activity(task, user, action_type, description, 
                      field_name=None, old_value=None, new_value=None):
    """
    Helper function to create activity log entries.
    
    Args:
        task: Task instance
        user: User who performed the action
        action_type: One of TaskActivity.ActionType choices
        description: Human-readable description
        field_name: Optional field name for field changes
        old_value: Optional previous value
        new_value: Optional new value
    
    Returns:
        Created TaskActivity instance
    """
    return TaskActivity.objects.create(
        task=task,
        user=user,
        action_type=action_type,
        description=description,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
    )
