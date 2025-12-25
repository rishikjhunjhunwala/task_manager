"""
Forms for departments app.
Will be expanded in Phase 4 (User & Department Management).
"""

from django import forms
from .models import Department


class DepartmentForm(forms.ModelForm):
    """Form for creating and editing departments."""
    
    class Meta:
        model = Department
        fields = ['name', 'code', 'head']
