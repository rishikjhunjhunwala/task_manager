"""
Forms for accounts app.

Phase 3: Authentication & Security forms including:
- LoginForm with domain validation
- PasswordChangeForm with history validation
- FirstLoginPasswordChangeForm for forced password change
- AdminUserCreationForm for admin user creation
"""

from django import forms
from django.contrib.auth import get_user_model, authenticate, password_validation
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, SetPasswordForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.conf import settings

from .validators import validate_email_domain

User = get_user_model()


class LoginForm(forms.Form):
    """
    Login form with email and password.
    
    Features:
    - Email domain validation (@centuryextrusions.com, @cnfcindia.com)
    - Account lockout display
    - Password expiry notification
    """
    
    email = forms.EmailField(
        label=_('Email Address'),
        max_length=254,
        widget=forms.EmailInput(attrs={
            'class': 'appearance-none rounded-none relative block w-full px-3 py-3 '
                     'border border-gray-300 placeholder-gray-500 text-gray-900 '
                     'rounded-t-md focus:outline-none focus:ring-indigo-500 '
                     'focus:border-indigo-500 focus:z-10 sm:text-sm',
            'placeholder': 'Email address',
            'autofocus': True,
        })
    )
    
    password = forms.CharField(
        label=_('Password'),
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'appearance-none rounded-none relative block w-full px-3 py-3 '
                     'border border-gray-300 placeholder-gray-500 text-gray-900 '
                     'rounded-b-md focus:outline-none focus:ring-indigo-500 '
                     'focus:border-indigo-500 focus:z-10 sm:text-sm',
            'placeholder': 'Password',
        })
    )
    
    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)
    
    def clean_email(self):
        """Validate email domain."""
        email = self.cleaned_data.get('email', '').lower().strip()
        
        if email:
            # Validate email domain
            allowed_domains = getattr(
                settings, 
                'ALLOWED_EMAIL_DOMAINS', 
                ['centuryextrusions.com', 'cnfcindia.com']
            )
            domain = email.split('@')[-1].lower()
            
            if domain not in allowed_domains:
                raise ValidationError(
                    _('Email domain must be one of: %(domains)s'),
                    code='invalid_domain',
                    params={'domains': ', '.join(allowed_domains)},
                )
        
        return email
    
    def clean(self):
        """Validate credentials and check account status."""
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')
        
        if email and password:
            # Try to get the user first to check lockout status
            try:
                user = User.objects.get(email__iexact=email)
                
                # Check if account is locked
                if user.is_locked():
                    from django.utils import timezone
                    remaining = (user.locked_until - timezone.now()).total_seconds()
                    minutes = int(remaining // 60) + 1
                    raise ValidationError(
                        _('Account is locked. Try again in %(minutes)d minute(s).'),
                        code='account_locked',
                        params={'minutes': minutes},
                    )
                
                # Check if account is active
                if not user.is_active:
                    raise ValidationError(
                        _('This account has been deactivated. Contact your administrator.'),
                        code='account_inactive',
                    )
                    
            except User.DoesNotExist:
                # Don't reveal that the user doesn't exist
                pass
            
            # Authenticate
            self.user_cache = authenticate(
                self.request,
                username=email,
                password=password
            )
            
            if self.user_cache is None:
                # Check if we need to show lockout warning
                try:
                    user = User.objects.get(email__iexact=email)
                    remaining_attempts = getattr(settings, 'LOCKOUT_THRESHOLD', 5) - user.failed_login_attempts
                    
                    if remaining_attempts > 0 and remaining_attempts <= 2:
                        raise ValidationError(
                            _('Invalid credentials. %(attempts)d attempt(s) remaining before lockout.'),
                            code='invalid_credentials_warning',
                            params={'attempts': remaining_attempts},
                        )
                except User.DoesNotExist:
                    pass
                
                raise ValidationError(
                    _('Invalid email or password. Please try again.'),
                    code='invalid_login',
                )
        
        return self.cleaned_data
    
    def get_user(self):
        """Return the authenticated user."""
        return self.user_cache


class PasswordChangeForm(forms.Form):
    """
    Password change form with validation.
    
    Features:
    - Current password verification
    - Password complexity validation
    - Password history check (cannot reuse last 5)
    - Confirmation field
    """
    
    current_password = forms.CharField(
        label=_('Current Password'),
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md '
                     'shadow-sm focus:outline-none focus:ring-indigo-500 '
                     'focus:border-indigo-500 sm:text-sm',
            'autocomplete': 'current-password',
        })
    )
    
    new_password = forms.CharField(
        label=_('New Password'),
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md '
                     'shadow-sm focus:outline-none focus:ring-indigo-500 '
                     'focus:border-indigo-500 sm:text-sm',
            'autocomplete': 'new-password',
        }),
        help_text=_(
            'Password must be at least 12 characters with uppercase, lowercase, '
            'number, and special character.'
        )
    )
    
    confirm_password = forms.CharField(
        label=_('Confirm New Password'),
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md '
                     'shadow-sm focus:outline-none focus:ring-indigo-500 '
                     'focus:border-indigo-500 sm:text-sm',
            'autocomplete': 'new-password',
        })
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_current_password(self):
        """Verify current password is correct."""
        current_password = self.cleaned_data.get('current_password')
        
        if current_password and not self.user.check_password(current_password):
            raise ValidationError(
                _('Your current password is incorrect.'),
                code='password_incorrect',
            )
        
        return current_password
    
    def clean_new_password(self):
        """Validate new password meets requirements."""
        new_password = self.cleaned_data.get('new_password')
        
        if new_password:
            # Run Django's password validators
            password_validation.validate_password(new_password, self.user)
            
            # Check password history
            if self.user.is_password_in_history(new_password):
                history_count = getattr(settings, 'PASSWORD_HISTORY_COUNT', 5)
                raise ValidationError(
                    _('You cannot reuse any of your last %(count)d passwords.'),
                    code='password_reused',
                    params={'count': history_count},
                )
            
            # Check it's not the same as current password
            if self.user.check_password(new_password):
                raise ValidationError(
                    _('New password must be different from your current password.'),
                    code='password_same',
                )
        
        return new_password
    
    def clean(self):
        """Verify passwords match."""
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password:
            if new_password != confirm_password:
                raise ValidationError(
                    _('The two password fields do not match.'),
                    code='password_mismatch',
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save the new password."""
        from django.utils import timezone
        from django.contrib.auth.hashers import make_password
        
        # Add current password to history before changing
        current_hash = self.user.password
        self.user.add_password_to_history(current_hash)
        
        # Set new password
        self.user.set_password(self.cleaned_data['new_password'])
        self.user.password_changed_at = timezone.now()
        self.user.must_change_password = False
        
        if commit:
            self.user.save()
        
        return self.user


class FirstLoginPasswordChangeForm(forms.Form):
    """
    Simplified password change form for first login.
    
    Does not require current password since user is using a temporary password.
    """
    
    new_password = forms.CharField(
        label=_('New Password'),
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md '
                     'shadow-sm focus:outline-none focus:ring-indigo-500 '
                     'focus:border-indigo-500 sm:text-sm',
            'autocomplete': 'new-password',
            'autofocus': True,
        }),
        help_text=_(
            'Password must be at least 12 characters with uppercase, lowercase, '
            'number, and special character.'
        )
    )
    
    confirm_password = forms.CharField(
        label=_('Confirm New Password'),
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md '
                     'shadow-sm focus:outline-none focus:ring-indigo-500 '
                     'focus:border-indigo-500 sm:text-sm',
            'autocomplete': 'new-password',
        })
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_new_password(self):
        """Validate new password meets requirements."""
        new_password = self.cleaned_data.get('new_password')
        
        if new_password:
            # Run Django's password validators
            password_validation.validate_password(new_password, self.user)
        
        return new_password
    
    def clean(self):
        """Verify passwords match."""
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password:
            if new_password != confirm_password:
                raise ValidationError(
                    _('The two password fields do not match.'),
                    code='password_mismatch',
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save the new password."""
        from django.utils import timezone
        
        # Set new password
        self.user.set_password(self.cleaned_data['new_password'])
        self.user.password_changed_at = timezone.now()
        self.user.must_change_password = False
        
        if commit:
            self.user.save()
        
        return self.user


class AdminUserCreationForm(UserCreationForm):
    """
    Form for admin to create new users.
    
    Features:
    - Email domain validation
    - Role selection
    - Department selection
    - Auto-generated temporary password option
    """
    
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'role', 'department')
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md '
                         'shadow-sm focus:outline-none focus:ring-indigo-500 '
                         'focus:border-indigo-500 sm:text-sm',
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md '
                         'shadow-sm focus:outline-none focus:ring-indigo-500 '
                         'focus:border-indigo-500 sm:text-sm',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md '
                         'shadow-sm focus:outline-none focus:ring-indigo-500 '
                         'focus:border-indigo-500 sm:text-sm',
            }),
            'role': forms.Select(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md '
                         'shadow-sm focus:outline-none focus:ring-indigo-500 '
                         'focus:border-indigo-500 sm:text-sm',
            }),
            'department': forms.Select(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md '
                         'shadow-sm focus:outline-none focus:ring-indigo-500 '
                         'focus:border-indigo-500 sm:text-sm',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make password fields optional (can auto-generate)
        self.fields['password1'].required = False
        self.fields['password2'].required = False
        self.fields['password1'].widget = forms.PasswordInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md '
                     'shadow-sm focus:outline-none focus:ring-indigo-500 '
                     'focus:border-indigo-500 sm:text-sm',
            'placeholder': 'Leave blank to auto-generate',
        })
        self.fields['password2'].widget = forms.PasswordInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md '
                     'shadow-sm focus:outline-none focus:ring-indigo-500 '
                     'focus:border-indigo-500 sm:text-sm',
            'placeholder': 'Confirm password',
        })
    
    def clean_email(self):
        """Validate email domain."""
        email = self.cleaned_data.get('email', '').lower().strip()
        
        if email:
            validate_email_domain(email)
            
            # Check for existing user
            if User.objects.filter(email__iexact=email).exists():
                raise ValidationError(
                    _('A user with this email already exists.'),
                    code='email_exists',
                )
        
        return email
    
    def clean(self):
        """Handle optional password - generate if not provided."""
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        # If no password provided, we'll generate one in save()
        if not password1 and not password2:
            # Clear any password errors since we'll auto-generate
            if 'password1' in self.errors:
                del self.errors['password1']
            if 'password2' in self.errors:
                del self.errors['password2']
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save user with password and must_change_password flag."""
        from .services import generate_temp_password
        
        user = super().save(commit=False)
        
        # Generate temporary password if not provided
        password = self.cleaned_data.get('password1')
        if not password:
            password = generate_temp_password()
        
        user.set_password(password)
        user.must_change_password = True
        user.is_active = True
        
        if commit:
            user.save()
        
        # Store the plain password for email sending (temporary)
        user._temp_password = password
        
        return user


class AdminUserChangeForm(UserChangeForm):
    """
    Form for admin to edit existing users.
    """
    
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'role', 'department', 'is_active')
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md '
                         'shadow-sm focus:outline-none focus:ring-indigo-500 '
                         'focus:border-indigo-500 sm:text-sm',
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md '
                         'shadow-sm focus:outline-none focus:ring-indigo-500 '
                         'focus:border-indigo-500 sm:text-sm',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md '
                         'shadow-sm focus:outline-none focus:ring-indigo-500 '
                         'focus:border-indigo-500 sm:text-sm',
            }),
            'role': forms.Select(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md '
                         'shadow-sm focus:outline-none focus:ring-indigo-500 '
                         'focus:border-indigo-500 sm:text-sm',
            }),
            'department': forms.Select(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md '
                         'shadow-sm focus:outline-none focus:ring-indigo-500 '
                         'focus:border-indigo-500 sm:text-sm',
            }),
        }
    
    def clean_email(self):
        """Validate email domain."""
        email = self.cleaned_data.get('email', '').lower().strip()
        
        if email:
            validate_email_domain(email)
            
            # Check for existing user (excluding current instance)
            existing = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError(
                    _('A user with this email already exists.'),
                    code='email_exists',
                )
        
        return email
