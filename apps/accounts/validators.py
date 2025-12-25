"""
Custom password validators for task_manager.

Requirements:
- Minimum 12 characters (handled by Django's MinimumLengthValidator)
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 number
- At least 1 special character
- Cannot reuse last 5 passwords
"""

import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class ComplexityValidator:
    """
    Validate that the password meets complexity requirements:
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """

    def __init__(self):
        self.requirements = [
            (r'[A-Z]', _('Password must contain at least one uppercase letter.')),
            (r'[a-z]', _('Password must contain at least one lowercase letter.')),
            (r'\d', _('Password must contain at least one digit.')),
            (r'[!@#$%^&*(),.?":{}|<>_+=~;\'"-]', 
             _('Password must contain at least one special character.')),
        ]

    def validate(self, password, user=None):
        errors = []
        for pattern, message in self.requirements:
            if not re.search(pattern, password):
                errors.append(ValidationError(message, code='password_complexity'))
        
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return _(
            "Your password must contain at least one uppercase letter, "
            "one lowercase letter, one digit, and one special character."
        )


class PasswordHistoryValidator:
    """
    Validate that the password hasn't been used in the last N passwords.
    This validator requires the user object to access password history.
    """

    def __init__(self, history_count=5):
        self.history_count = history_count

    def validate(self, password, user=None):
        if user is None:
            return
        
        # Check if user has the password_history attribute
        if not hasattr(user, 'password_history'):
            return
        
        # Check if password matches any in history
        if user.is_password_in_history(password):
            raise ValidationError(
                _(f"You cannot reuse any of your last {self.history_count} passwords."),
                code='password_reused',
            )

    def get_help_text(self):
        return _(
            f"Your password cannot be the same as any of your last "
            f"{self.history_count} passwords."
        )


def validate_email_domain(email):
    """
    Validate that the email domain is in the allowed list.
    Allowed domains: @centuryextrusions.com, @cnfcindia.com
    """
    from django.conf import settings
    
    allowed_domains = getattr(
        settings, 
        'ALLOWED_EMAIL_DOMAINS', 
        ['centuryextrusions.com', 'cnfcindia.com']
    )
    
    domain = email.split('@')[-1].lower()
    
    if domain not in allowed_domains:
        raise ValidationError(
            _(f"Email domain must be one of: {', '.join(allowed_domains)}"),
            code='invalid_email_domain',
        )
