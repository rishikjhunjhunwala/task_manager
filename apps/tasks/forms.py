"""
Forms for tasks app.

TaskForm: Create/edit task with dynamic assignee dropdown based on user role
CommentForm: Add comments to tasks
AttachmentForm: Upload file attachments
"""

from django import forms
from django.utils import timezone

from .models import Task, Comment, Attachment
from .permissions import get_assignable_users
from apps.accounts.models import User


class TaskForm(forms.ModelForm):
    """
    Form for creating and editing tasks.
    
    The assignee dropdown is dynamically filtered based on the current user's role:
    - Employee: Only self
    - Manager: Self + department members
    - Senior Manager/Admin: All active users
    """
    
    class Meta:
        model = Task
        fields = ['title', 'description', 'assignee', 'priority', 'deadline']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
                'placeholder': 'Enter task title...',
                'autofocus': True,
            }),
            'description': forms.Textarea(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
                'rows': 4,
                'placeholder': 'Enter task description (optional)...',
            }),
            'assignee': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            }),
            'priority': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            }),
            'deadline': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            }),
        }
        labels = {
            'title': 'Task Title',
            'description': 'Description',
            'assignee': 'Assign To',
            'priority': 'Priority',
            'deadline': 'Deadline',
        }
        help_texts = {
            'deadline': 'Optional. Date and time when this task is due.',
        }
    
    def __init__(self, *args, user=None, **kwargs):
        """
        Initialize form with role-based assignee filtering.
        
        Args:
            user: Current user (required for filtering assignees)
        """
        super().__init__(*args, **kwargs)
        
        self.user = user
        
        if user:
            # Filter assignee choices based on user's role
            assignable_users = get_assignable_users(user)
            
            # Format choices with department info
            choices = []
            for u in assignable_users:
                dept_name = u.department.code if u.department else 'No Dept'
                if u.pk == user.pk:
                    label = f"{u.get_full_name()} (Myself)"
                else:
                    label = f"{u.get_full_name()} ({dept_name})"
                choices.append((u.pk, label))
            
            self.fields['assignee'].choices = choices
            
            # Set default to self
            if not self.instance.pk:  # Only for new tasks
                self.fields['assignee'].initial = user.pk
        
        # Make deadline not required
        self.fields['deadline'].required = False
    
    def clean_title(self):
        """Validate and clean title."""
        title = self.cleaned_data.get('title', '').strip()
        if not title:
            raise forms.ValidationError("Task title is required.")
        if len(title) > 255:
            raise forms.ValidationError("Title cannot exceed 255 characters.")
        return title
    
    def clean_deadline(self):
        """Validate deadline is in the future for new tasks."""
        deadline = self.cleaned_data.get('deadline')
        
        if deadline:
            # For new tasks, deadline must be in the future
            if not self.instance.pk and deadline < timezone.now():
                raise forms.ValidationError("Deadline cannot be in the past.")
            
            # For existing tasks, allow past deadline only if it hasn't changed
            if self.instance.pk:
                if deadline < timezone.now() and deadline != self.instance.deadline:
                    raise forms.ValidationError("Deadline cannot be in the past.")
        
        return deadline
    
    def clean_assignee(self):
        """Validate assignee against user's permissions."""
        assignee = self.cleaned_data.get('assignee')
        
        if not assignee:
            raise forms.ValidationError("Please select an assignee.")
        
        # The queryset is already filtered, but double-check for security
        if self.user:
            assignable = get_assignable_users(self.user)
            if not assignable.filter(pk=assignee.pk).exists():
                raise forms.ValidationError(
                    "You don't have permission to assign tasks to this user."
                )
        
        return assignee


class TaskEditForm(forms.ModelForm):
    """
    Form for editing existing tasks.
    Similar to TaskForm but excludes assignee (use reassign for that).
    """
    
    class Meta:
        model = Task
        fields = ['title', 'description', 'priority', 'deadline']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            }),
            'description': forms.Textarea(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
                'rows': 4,
            }),
            'priority': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            }),
            'deadline': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['deadline'].required = False
        
        # Format initial deadline for datetime-local input
        if self.instance.deadline:
            self.initial['deadline'] = self.instance.deadline.strftime('%Y-%m-%dT%H:%M')
    
    def clean_deadline(self):
        """Allow past deadlines for edits (they may already be overdue)."""
        deadline = self.cleaned_data.get('deadline')
        return deadline


class ReassignTaskForm(forms.Form):
    """
    Form for reassigning a task to a different user.
    """
    
    new_assignee = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label='Reassign To',
        widget=forms.Select(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        })
    )
    
    def __init__(self, *args, user=None, task=None, **kwargs):
        """
        Initialize with filtered assignee choices.
        
        Args:
            user: Current user performing reassignment
            task: Task being reassigned
        """
        super().__init__(*args, **kwargs)
        
        self.user = user
        self.task = task
        
        if user:
            # Get assignable users, excluding current assignee
            assignable_users = get_assignable_users(user)
            if task:
                assignable_users = assignable_users.exclude(pk=task.assignee_id)
            
            self.fields['new_assignee'].queryset = assignable_users
            
            # Custom label format
            choices = [('', '-- Select User --')]
            for u in assignable_users:
                dept_name = u.department.code if u.department else 'No Dept'
                choices.append((u.pk, f"{u.get_full_name()} ({dept_name})"))
            
            self.fields['new_assignee'].choices = choices


class CancelTaskForm(forms.Form):
    """
    Form for cancelling a task with optional reason.
    """
    
    reason = forms.CharField(
        required=False,
        max_length=500,
        label='Cancellation Reason',
        widget=forms.Textarea(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            'rows': 3,
            'placeholder': 'Optional: Explain why this task is being cancelled...',
        })
    )


class StatusChangeForm(forms.Form):
    """
    Form for changing task status.
    Shows only valid transitions based on current status.
    """
    
    STATUS_CHOICES = [
        ('in_progress', 'Start Working (In Progress)'),
        ('completed', 'Mark as Completed'),
        ('verified', 'Verify Task'),
    ]
    
    new_status = forms.ChoiceField(
        choices=[],
        label='Change Status To',
        widget=forms.Select(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        })
    )
    
    def __init__(self, *args, task=None, user=None, **kwargs):
        """
        Initialize with valid status transitions.
        
        Args:
            task: Task being updated
            user: Current user
        """
        super().__init__(*args, **kwargs)
        
        self.task = task
        self.user = user
        
        if task:
            # Build valid choices based on current status and user permissions
            choices = []
            
            next_status = task.get_next_status()
            if next_status:
                # Standard forward transition
                if next_status == 'in_progress':
                    choices.append(('in_progress', 'Start Working'))
                elif next_status == 'completed':
                    choices.append(('completed', 'Mark as Completed'))
                elif next_status == 'verified':
                    # Only creator can verify
                    if user and (task.created_by_id == user.pk or user.role == 'admin'):
                        choices.append(('verified', 'Verify & Close'))
            
            self.fields['new_status'].choices = choices


class CommentForm(forms.ModelForm):
    """Form for adding comments to tasks."""
    
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
                'rows': 3,
                'placeholder': 'Add a comment...',
            }),
        }
        labels = {
            'content': '',
        }
    
    def clean_content(self):
        """Validate comment is not empty."""
        content = self.cleaned_data.get('content', '').strip()
        if not content:
            raise forms.ValidationError("Comment cannot be empty.")
        return content


class AttachmentForm(forms.ModelForm):
    """Form for uploading attachments."""
    
    class Meta:
        model = Attachment
        fields = ['file']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100',
                'accept': '.pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg,.txt',
            }),
        }
        labels = {
            'file': 'Attachment',
        }
        help_texts = {
            'file': f'Max {Attachment.MAX_SIZE_MB} MB. Allowed: PDF, DOC, DOCX, XLS, XLSX, PNG, JPG, JPEG, TXT',
        }
    
    def clean_file(self):
        """Validate file size and type."""
        file = self.cleaned_data.get('file')
        
        if file:
            # Check size
            if file.size > Attachment.MAX_SIZE_BYTES:
                raise forms.ValidationError(
                    f"File size cannot exceed {Attachment.MAX_SIZE_MB} MB. "
                    f"Your file is {file.size / (1024*1024):.1f} MB."
                )
            
            # Check extension
            import os
            ext = os.path.splitext(file.name)[1].lower().lstrip('.')
            if ext not in Attachment.ALLOWED_EXTENSIONS:
                allowed = ', '.join(Attachment.ALLOWED_EXTENSIONS).upper()
                raise forms.ValidationError(
                    f"File type '.{ext}' is not allowed. Allowed types: {allowed}"
                )
        
        return file
