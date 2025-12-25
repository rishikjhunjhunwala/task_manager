"""
Forms for tasks app.
Will be expanded in Phase 5 (Core Task Management).
"""

from django import forms
from .models import Task, Comment, Attachment


class TaskForm(forms.ModelForm):
    """Form for creating and editing tasks."""
    
    class Meta:
        model = Task
        fields = ['title', 'description', 'assignee', 'priority', 'deadline']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'deadline': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }


class CommentForm(forms.ModelForm):
    """Form for adding comments to tasks."""
    
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Add a comment...'}),
        }


class AttachmentForm(forms.ModelForm):
    """Form for uploading attachments."""
    
    class Meta:
        model = Attachment
        fields = ['file']
