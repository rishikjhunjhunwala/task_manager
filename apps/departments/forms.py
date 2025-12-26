"""
Forms for departments app.

Includes validation for department head role.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import Department

User = get_user_model()


class DepartmentForm(forms.ModelForm):
    """
    Form for creating and editing departments.
    Validates that head is Manager or Senior Manager.
    """
    
    class Meta:
        model = Department
        fields = ['name', 'code', 'head']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
                'placeholder': 'e.g., Engineering',
            }),
            'code': forms.TextInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
                'placeholder': 'e.g., ENG',
                'style': 'text-transform: uppercase;',
            }),
            'head': forms.Select(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter head choices to only show eligible users
        eligible_roles = ['manager', 'senior_manager_1', 'senior_manager_2']
        self.fields['head'].queryset = User.objects.filter(
            role__in=eligible_roles,
            is_active=True
        ).order_by('first_name', 'last_name')
        
        self.fields['head'].required = False
        self.fields['head'].empty_label = '-- Select Department Head (Optional) --'
        
        # Add help text
        self.fields['code'].help_text = 'Short identifier (e.g., ENG, HR, FIN). Will be converted to uppercase.'
        self.fields['head'].help_text = 'Must be Manager, Senior Manager 1, or Senior Manager 2.'
    
    def clean_code(self):
        """Convert code to uppercase."""
        code = self.cleaned_data.get('code')
        if code:
            code = code.upper().strip()
            
            # Check for uniqueness (excluding current instance)
            existing = Department.objects.filter(code__iexact=code)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError('A department with this code already exists.')
        
        return code
    
    def clean_name(self):
        """Validate department name uniqueness."""
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip()
            
            # Check for uniqueness (excluding current instance)
            existing = Department.objects.filter(name__iexact=name)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError('A department with this name already exists.')
        
        return name
    
    def clean_head(self):
        """Validate that head has appropriate role."""
        head = self.cleaned_data.get('head')
        
        if head:
            eligible_roles = ['manager', 'senior_manager_1', 'senior_manager_2']
            if head.role not in eligible_roles:
                raise ValidationError(
                    'Department head must be Manager, Senior Manager 1, or Senior Manager 2.'
                )
            
            if not head.is_active:
                raise ValidationError('Department head must be an active user.')
        
        return head
