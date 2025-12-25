"""
Task management models.

Models:
- Task: Main task with reference number, status workflow, escalation tracking
- Comment: Task comments
- Attachment: Single file attachment per task (max 2 MB)
"""

import os
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError


def attachment_upload_path(instance, filename):
    """Generate upload path for attachments: media/attachments/YYYY/MM/task_id/filename"""
    date = timezone.now()
    return f"attachments/{date.year}/{date.month:02d}/{instance.task_id}/{filename}"


class Task(models.Model):
    """
    Main Task model.
    
    Reference number format: TASK-YYYYMMDD-XXXX
    Task types: personal (self-assigned) vs delegated (assigned by someone else)
    
    Status workflow:
    - Delegated: pending → in_progress → completed → verified
    - Personal: pending → in_progress → completed (no verification)
    - Any status can transition to cancelled
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        VERIFIED = 'verified', 'Verified'
        CANCELLED = 'cancelled', 'Cancelled'

    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        CRITICAL = 'critical', 'Critical'

    class TaskType(models.TextChoices):
        PERSONAL = 'personal', 'Personal'
        DELEGATED = 'delegated', 'Delegated'

    class Source(models.TextChoices):
        MANUAL = 'manual', 'Manual'
        EMAIL = 'email', 'Email'  # For Phase 2

    # Core fields
    reference_number = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        db_index=True,
        help_text='Auto-generated: TASK-YYYYMMDD-XXXX'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Relationships
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='assigned_tasks',
        help_text='User assigned to complete this task'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_tasks',
        help_text='User who created this task'
    )
    department = models.ForeignKey(
        'departments.Department',
        on_delete=models.PROTECT,
        related_name='tasks',
        help_text='Auto-populated from assignee'
    )

    # Task classification
    task_type = models.CharField(
        max_length=10,
        choices=TaskType.choices,
        editable=False,
        help_text='Auto-set: personal if assignee==creator, else delegated'
    )
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        db_index=True,
    )

    # Deadline and timing
    deadline = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Date and time (IST) when task is due'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancelled_tasks',
    )

    # Notification tracking
    deadline_reminder_sent = models.BooleanField(
        default=False,
        help_text='24-hour deadline reminder sent'
    )
    first_overdue_email_sent = models.BooleanField(
        default=False,
        help_text='First overdue notification sent'
    )

    # Escalation tracking
    escalated_to_sm2_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='72-hour escalation to Senior Manager 2'
    )
    escalated_to_sm1_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='120-hour escalation to Senior Manager 1'
    )

    # Source tracking (for Phase 2 email ingestion)
    source = models.CharField(
        max_length=10,
        choices=Source.choices,
        default=Source.MANUAL,
    )
    source_reference = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text='Email ID reference for Phase 2'
    )

    class Meta:
        verbose_name = 'task'
        verbose_name_plural = 'tasks'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'assignee']),
            models.Index(fields=['status', 'created_by']),
            models.Index(fields=['deadline', 'status']),
            models.Index(fields=['department', 'status']),
            models.Index(fields=['reference_number']),
        ]

    def __str__(self):
        return f"{self.reference_number}: {self.title}"

    def save(self, *args, **kwargs):
        # Auto-set task_type based on assignee vs creator
        if self.assignee_id and self.created_by_id:
            self.task_type = (
                self.TaskType.PERSONAL 
                if self.assignee_id == self.created_by_id 
                else self.TaskType.DELEGATED
            )
        
        # Auto-populate department from assignee
        if self.assignee_id and hasattr(self.assignee, 'department'):
            self.department = self.assignee.department

        # Generate reference number if not set
        if not self.reference_number:
            self.reference_number = self._generate_reference_number()

        super().save(*args, **kwargs)

    def _generate_reference_number(self):
        """Generate unique reference number: TASK-YYYYMMDD-XXXX"""
        today = timezone.now().strftime('%Y%m%d')
        prefix = f'TASK-{today}'
        
        # Count existing tasks with same prefix
        count = Task.objects.filter(
            reference_number__startswith=prefix
        ).count() + 1
        
        return f'{prefix}-{count:04d}'

    # ==========================================================================
    # Status Properties
    # ==========================================================================

    @property
    def is_personal(self):
        """Check if this is a personal task."""
        return self.task_type == self.TaskType.PERSONAL

    @property
    def is_delegated(self):
        """Check if this is a delegated task."""
        return self.task_type == self.TaskType.DELEGATED

    @property
    def is_overdue(self):
        """Check if task is past deadline and not completed."""
        if not self.deadline:
            return False
        if self.status in [self.Status.COMPLETED, self.Status.VERIFIED, self.Status.CANCELLED]:
            return False
        return timezone.now() > self.deadline

    @property
    def is_escalated(self):
        """Check if task has been escalated (72+ hours overdue)."""
        return self.escalated_to_sm2_at is not None or self.escalated_to_sm1_at is not None

    @property
    def hours_overdue(self):
        """Calculate hours overdue. Returns 0 if not overdue."""
        if not self.is_overdue:
            return 0
        delta = timezone.now() - self.deadline
        return delta.total_seconds() / 3600

    @property
    def escalation_level(self):
        """Return current escalation level (0, 1, or 2)."""
        if self.escalated_to_sm1_at:
            return 2  # 120+ hours
        if self.escalated_to_sm2_at:
            return 1  # 72+ hours
        return 0

    # ==========================================================================
    # Status Workflow Methods
    # ==========================================================================

    def can_transition_to(self, new_status):
        """Check if status transition is valid."""
        # Cancelled and Verified are terminal states
        if self.status in [self.Status.CANCELLED, self.Status.VERIFIED]:
            return False
        
        # Personal tasks: completed is terminal
        if self.is_personal and self.status == self.Status.COMPLETED:
            return False
        
        # Any status can go to cancelled
        if new_status == self.Status.CANCELLED:
            return True
        
        # Valid forward transitions
        valid_transitions = {
            self.Status.PENDING: [self.Status.IN_PROGRESS],
            self.Status.IN_PROGRESS: [self.Status.COMPLETED],
            self.Status.COMPLETED: [self.Status.VERIFIED] if self.is_delegated else [],
        }
        
        return new_status in valid_transitions.get(self.status, [])

    def get_next_status(self):
        """Get the next logical status for this task."""
        if self.status == self.Status.PENDING:
            return self.Status.IN_PROGRESS
        elif self.status == self.Status.IN_PROGRESS:
            return self.Status.COMPLETED
        elif self.status == self.Status.COMPLETED and self.is_delegated:
            return self.Status.VERIFIED
        return None


class Comment(models.Model):
    """
    Task comment model.
    
    Comments are displayed chronologically on task detail page.
    """
    
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='comments',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='task_comments',
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'comment'
        verbose_name_plural = 'comments'
        ordering = ['created_at']  # Chronological order

    def __str__(self):
        return f"Comment by {self.author} on {self.task.reference_number}"


class Attachment(models.Model):
    """
    Task attachment model.
    
    Rules:
    - Maximum 1 attachment per task (OneToOne)
    - Maximum file size: 2 MB
    - Allowed types: PDF, DOC, DOCX, XLS, XLSX, PNG, JPG, JPEG, TXT
    """
    
    ALLOWED_EXTENSIONS = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'png', 'jpg', 'jpeg', 'txt']
    MAX_SIZE_MB = 2
    MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024

    task = models.OneToOneField(
        Task,
        on_delete=models.CASCADE,
        related_name='attachment',
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_attachments',
    )
    file = models.FileField(
        upload_to=attachment_upload_path,
        validators=[
            FileExtensionValidator(allowed_extensions=ALLOWED_EXTENSIONS)
        ],
    )
    filename = models.CharField(
        max_length=255,
        help_text='Original filename'
    )
    file_size = models.PositiveIntegerField(
        help_text='File size in bytes'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'attachment'
        verbose_name_plural = 'attachments'

    def __str__(self):
        return f"Attachment: {self.filename} for {self.task.reference_number}"

    def clean(self):
        """Validate file size."""
        if self.file and self.file.size > self.MAX_SIZE_BYTES:
            raise ValidationError(
                f'File size cannot exceed {self.MAX_SIZE_MB} MB.'
            )

    def save(self, *args, **kwargs):
        # Store original filename and size before saving
        if self.file:
            self.filename = os.path.basename(self.file.name)
            self.file_size = self.file.size
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Delete file from storage when model is deleted."""
        if self.file:
            storage = self.file.storage
            if storage.exists(self.file.name):
                storage.delete(self.file.name)
        super().delete(*args, **kwargs)

    @property
    def file_size_display(self):
        """Return human-readable file size."""
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / (1024 * 1024):.1f} MB"

    @property
    def extension(self):
        """Return file extension."""
        return os.path.splitext(self.filename)[1].lower()
