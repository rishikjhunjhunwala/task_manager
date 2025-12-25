"""
Forms for accounts app.
Will be expanded in Phase 3 (Authentication & Security).
"""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

from .validators import validate_email_domain

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    """
    Form for creating new users with email domain validation.
    """
    
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'role', 'department')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            validate_email_domain(email)
        return email


class CustomUserChangeForm(UserChangeForm):
    """
    Form for updating users with email domain validation.
    """
    
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'role', 'department', 'is_active')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            validate_email_domain(email)
        return email
