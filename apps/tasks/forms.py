"""
Forms for tasks app.

Includes:
- TaskForm: Create and edit tasks with role-based assignee filtering
- CommentForm: Add comments to tasks
- AttachmentForm: Upload attachments
- TaskStatusForm: Change task status
"""

from django import forms
from django.core.exceptions import ValidationError

from .models import Task, Comment, Attachment
from .permissions import get_assignable_users
from apps.accounts.models import User


class TaskForm(forms.ModelForm):
    """
    Form for creating and editing tasks.
    
    The assignee field is dynamically populated based on the user's role:
    - Employee: Can only assign to themselves
    - Manager: Can assign to self + department users
    - Senior Manager/Admin: Can assign to anyone
    """
    
    class Meta:
        model = Task
        fields = ['title', 'description', 'assignee', 'priority', 'deadline']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
                'placeholder': 'Enter task title...',
            }),
            'description': forms.Textarea(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
                'rows': 4,
                'placeholder': 'Describe the task...',
            }),
            'priority': forms.Select(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            }),
            'deadline': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            }),
            'assignee': forms.Select(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        """
        Initialize form with user context for role-based filtering.
        
        Args:
            user: Current logged-in user (required)
        """
        super().__init__(*args, **kwargs)
        self.user = user
        
        if user:
            # Get assignable users based on role
            assignable_users = get_assignable_users(user)
            self.fields['assignee'].queryset = assignable_users
            
            # Set default assignee to self
            if not self.instance.pk:  # Only for new tasks
                self.fields['assignee'].initial = user
            
            # Format assignee choices with department
            self.fields['assignee'].label_from_instance = lambda obj: (
                f"{obj.get_full_name()} ({obj.department.name})" if obj.department 
                else obj.get_full_name()
            )
        
        # Make deadline optional
        self.fields['deadline'].required = False
        
        # Help text
        self.fields['title'].help_text = 'Brief, descriptive title for the task'
        self.fields['deadline'].help_text = 'Leave empty for tasks without deadline'

    def clean_deadline(self):
        """Validate deadline is not in the past for new tasks."""
        deadline = self.cleaned_data.get('deadline')
        
        if deadline and not self.instance.pk:  # New task
            from django.utils import timezone
            if deadline < timezone.now():
                raise ValidationError("Deadline cannot be in the past")
        
        return deadline


class CommentForm(forms.ModelForm):
    """Form for adding comments to tasks."""
    
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
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
            raise ValidationError("Comment cannot be empty")
        return content


class AttachmentForm(forms.ModelForm):
    """Form for uploading attachments."""
    
    class Meta:
        model = Attachment
        fields = ['file']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100',
                'accept': '.pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg,.txt',
            }),
        }

    def clean_file(self):
        """Validate file size and type."""
        file = self.cleaned_data.get('file')
        
        if file:
            # Check file size
            if file.size > Attachment.MAX_SIZE_BYTES:
                raise ValidationError(
                    f"File size cannot exceed {Attachment.MAX_SIZE_MB} MB. "
                    f"Your file is {file.size / (1024 * 1024):.1f} MB."
                )
            
            # Check file extension
            import os
            ext = os.path.splitext(file.name)[1].lower().lstrip('.')
            if ext not in Attachment.ALLOWED_EXTENSIONS:
                raise ValidationError(
                    f"File type '{ext}' is not allowed. "
                    f"Allowed types: {', '.join(Attachment.ALLOWED_EXTENSIONS)}"
                )
        
        return file


class TaskStatusForm(forms.Form):
    """
    Form for changing task status.
    
    Available status choices depend on:
    - Current task status
    - Task type (personal vs delegated)
    - User role
    """
    
    status = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={
            'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        })
    )

    def __init__(self, *args, task=None, user=None, **kwargs):
        """
        Initialize form with task and user context.
        
        Args:
            task: Task instance
            user: Current logged-in user
        """
        super().__init__(*args, **kwargs)
        self.task = task
        self.user = user
        
        if task:
            self.fields['status'].choices = self._get_status_choices()

    def _get_status_choices(self):
        """Get available status choices based on current task state."""
        choices = []
        task = self.task
        
        if not task:
            return choices
        
        # Current status (always shown)
        choices.append((task.status, f'{task.get_status_display()} (Current)'))
        
        # Get valid transitions
        if task.status == 'pending':
            choices.append(('in_progress', 'In Progress'))
            choices.append(('cancelled', 'Cancelled'))
        
        elif task.status == 'in_progress':
            choices.append(('completed', 'Completed'))
            choices.append(('cancelled', 'Cancelled'))
        
        elif task.status == 'completed':
            if task.task_type == 'delegated':
                # Only creator or admin can verify
                if self.user and (self.user.pk == task.created_by_id or self.user.role == 'admin'):
                    choices.append(('verified', 'Verified'))
            # Personal tasks: completed is terminal (no verify option)
        
        return choices

    def clean_status(self):
        """Validate status transition."""
        new_status = self.cleaned_data.get('status')
        
        if self.task and new_status != self.task.status:
            if not self.task.can_transition_to(new_status):
                raise ValidationError(
                    f"Cannot change status from {self.task.get_status_display()} "
                    f"to {dict(Task.Status.choices).get(new_status)}"
                )
        
        return new_status


class TaskReassignForm(forms.Form):
    """Form for reassigning a task to a different user."""
    
    assignee = forms.ModelChoiceField(
        queryset=User.objects.none(),
        widget=forms.Select(attrs={
            'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        }),
        label='New Assignee'
    )

    def __init__(self, *args, task=None, user=None, **kwargs):
        """
        Initialize form with task and user context.
        
        Args:
            task: Task instance to reassign
            user: Current logged-in user
        """
        super().__init__(*args, **kwargs)
        self.task = task
        self.user = user
        
        if user:
            # Get assignable users excluding current assignee
            assignable = get_assignable_users(user)
            if task:
                assignable = assignable.exclude(pk=task.assignee_id)
            self.fields['assignee'].queryset = assignable
            
            # Format choices with department
            self.fields['assignee'].label_from_instance = lambda obj: (
                f"{obj.get_full_name()} ({obj.department.name})" if obj.department 
                else obj.get_full_name()
            )


class TaskCancelForm(forms.Form):
    """Form for cancelling a task with optional reason."""
    
    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            'rows': 3,
            'placeholder': 'Reason for cancellation (optional)...',
        }),
        label='Cancellation Reason'
    )
