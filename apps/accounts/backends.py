"""
Custom authentication backend for email-based login with lockout handling.

Phase 3: Enhanced with lockout notification.
"""

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone

User = get_user_model()


class EmailAuthBackend(ModelBackend):
    """
    Authenticate using email address instead of username.
    Includes account lockout logic after failed attempts.
    
    Features:
    - Email-based authentication (case-insensitive)
    - Account lockout after 5 failed attempts
    - 15-minute lockout duration
    - Lockout notification email
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate a user by email and password.
        
        Args:
            request: The HTTP request
            username: Actually the email address (Django's default parameter name)
            password: The password to verify
        
        Returns:
            User object if authentication succeeds, None otherwise
        """
        # Allow email to be passed as either 'username' or 'email'
        email = kwargs.get('email') or username
        
        if email is None or password is None:
            return None

        # Normalize email
        email = email.lower().strip()

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # Run the default password hasher to mitigate timing attacks
            User().set_password(password)
            return None

        # Check if account is locked
        if user.is_locked():
            return None

        # Check if account is active
        if not user.is_active:
            return None

        # Verify password
        if user.check_password(password):
            # Successful login - reset failed attempts
            user.reset_failed_logins()
            return user
        else:
            # Failed login - record attempt and possibly lock
            self._handle_failed_login(user)
            return None

    def _handle_failed_login(self, user):
        """
        Handle a failed login attempt.
        Records the attempt and locks the account if threshold is exceeded.
        """
        user.record_failed_login()
        
        lockout_threshold = getattr(settings, 'LOCKOUT_THRESHOLD', 5)
        lockout_duration = getattr(settings, 'LOCKOUT_DURATION', 15 * 60)  # 15 minutes
        
        if user.failed_login_attempts >= lockout_threshold:
            user.lock_account(lockout_duration)
            
            # Send lockout notification email
            self._send_lockout_notification(user)
    
    def _send_lockout_notification(self, user):
        """Send email notification when account is locked."""
        try:
            from apps.accounts.services import send_lockout_notification
            send_lockout_notification(user)
        except Exception:
            # Don't fail authentication if email fails
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f'Failed to send lockout notification to {user.email}')

    def get_user(self, user_id):
        """
        Retrieve a user by their primary key.
        """
        try:
            user = User.objects.get(pk=user_id)
            return user if self.user_can_authenticate(user) else None
        except User.DoesNotExist:
            return None

    def user_can_authenticate(self, user):
        """
        Reject users with is_active=False or locked accounts.
        """
        is_active = getattr(user, 'is_active', None)
        return is_active and not user.is_locked()
