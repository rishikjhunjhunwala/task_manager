"""
Forms for accounts app.
Includes authentication forms and admin user management forms.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .validators import validate_email_domain

User = get_user_model()


# =============================================================================
# Authentication Forms
# =============================================================================

class LoginForm(forms.Form):
    """
    Custom login form with email validation.
    """
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'appearance-none rounded-none relative block w-full px-3 py-3 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm',
            'placeholder': 'Email address',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'appearance-none rounded-none relative block w-full px-3 py-3 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-b-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm',
            'placeholder': 'Password',
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Validate domain
            validate_email_domain(email)
        return email.lower()


class PasswordChangeForm(forms.Form):
    """
    Form for changing password with validation.
    """
    current_password = forms.CharField(
        label='Current Password',
        widget=forms.PasswordInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
            'placeholder': 'Enter current password',
        })
    )
    new_password = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
            'placeholder': 'Enter new password',
        }),
        help_text='12+ characters with uppercase, lowercase, number, and special character.'
    )
    confirm_password = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
            'placeholder': 'Confirm new password',
        })
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        current = self.cleaned_data.get('current_password')
        if not self.user.check_password(current):
            raise ValidationError('Current password is incorrect.')
        return current

    def clean_new_password(self):
        password = self.cleaned_data.get('new_password')
        # Run Django's password validators
        validate_password(password, self.user)
        # Check password history
        if self.user.is_password_in_history(password):
            raise ValidationError('You cannot reuse any of your last 5 passwords.')
        return password

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password:
            if new_password != confirm_password:
                raise ValidationError({'confirm_password': 'Passwords do not match.'})
        return cleaned_data


class FirstLoginPasswordChangeForm(forms.Form):
    """
    Form for first login password change (no current password required).
    """
    new_password = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
            'placeholder': 'Enter new password',
            'autofocus': True,
        }),
        help_text='12+ characters with uppercase, lowercase, number, and special character.'
    )
    confirm_password = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
            'placeholder': 'Confirm new password',
        })
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_new_password(self):
        password = self.cleaned_data.get('new_password')
        validate_password(password, self.user)
        return password

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password:
            if new_password != confirm_password:
                raise ValidationError({'confirm_password': 'Passwords do not match.'})
        return cleaned_data


# =============================================================================
# Admin User Management Forms
# =============================================================================

class AdminUserCreationForm(forms.ModelForm):
    """
    Form for Admin to create new users.
    Generates temporary password automatically.
    """
    
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'role', 'department')
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
                'placeholder': 'user@centuryextrusions.com',
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
                'placeholder': 'First name',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
                'placeholder': 'Last name',
            }),
            'role': forms.Select(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
            }),
            'department': forms.Select(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['department'].required = False
        self.fields['department'].empty_label = '-- Select Department --'
        
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower()
            validate_email_domain(email)
            # Check for existing user
            if User.objects.filter(email__iexact=email).exists():
                raise ValidationError('A user with this email already exists.')
        return email


class AdminUserEditForm(forms.ModelForm):
    """
    Form for Admin to edit existing users.
    Does not include password fields - password reset is separate.
    """
    
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'role', 'department', 'is_active')
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
            }),
            'role': forms.Select(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
            }),
            'department': forms.Select(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['department'].required = False
        self.fields['department'].empty_label = '-- Select Department --'
        
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower()
            validate_email_domain(email)
            # Check for existing user (excluding current instance)
            existing = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError('A user with this email already exists.')
        return email


# =============================================================================
# Legacy Forms (for Django Admin compatibility)
# =============================================================================

class CustomUserCreationForm(UserCreationForm):
    """
    Form for creating new users via Django Admin.
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
    Form for updating users via Django Admin.
    """
    
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'role', 'department', 'is_active')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            validate_email_domain(email)
        return email
