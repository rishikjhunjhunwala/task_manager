"""
Service layer for accounts app.

Business logic for:
- Temporary password generation
- Account unlock
- Welcome email sending
- Password reset
- Session management
"""

import secrets
import string
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth import get_user_model


User = get_user_model()


def generate_temp_password(length=16):
    """
    Generate a temporary password that meets complexity requirements.
    
    Requirements:
    - At least 12 characters (we use 16 for extra security)
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 digit
    - At least 1 special character
    
    Returns:
        str: A randomly generated password
    """
    # Define character sets
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special = '!@#$%^&*()_+-=[]{}|;:,.<>?'
    
    # Ensure at least one of each required type
    password = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(special),
    ]
    
    # Fill the rest with a mix of all characters
    all_chars = uppercase + lowercase + digits + special
    remaining_length = length - len(password)
    password.extend(secrets.choice(all_chars) for _ in range(remaining_length))
    
    # Shuffle to avoid predictable positions
    password_list = list(password)
    secrets.SystemRandom().shuffle(password_list)
    
    return ''.join(password_list)


def unlock_account(user):
    """
    Manually unlock a user account.
    
    Args:
        user: User instance to unlock
    
    Returns:
        bool: True if account was locked and is now unlocked
    """
    was_locked = user.is_locked()
    user.unlock_account()
    return was_locked


def reset_user_password(user, send_email=True):
    """
    Reset a user's password to a temporary password.
    
    Args:
        user: User instance
        send_email: Whether to send the new password via email
    
    Returns:
        str: The new temporary password
    """
    # Generate new temporary password
    temp_password = generate_temp_password()
    
    # Set password and require change on next login
    user.set_password(temp_password)
    user.must_change_password = True
    user.failed_login_attempts = 0
    user.locked_until = None
    user.save()
    
    # Send email with new password
    if send_email:
        send_password_reset_email(user, temp_password)
    
    return temp_password


def send_welcome_email(user, temp_password):
    """
    Send welcome email to new user with login credentials.
    
    Args:
        user: User instance
        temp_password: The temporary password to include
    """
    subject = 'Welcome to Task Manager - Your Account Details'
    
    context = {
        'user': user,
        'temp_password': temp_password,
        'login_url': getattr(settings, 'SITE_URL', 'http://localhost:8000') + '/login/',
        'support_email': getattr(settings, 'SUPPORT_EMAIL', 'admin@centuryextrusions.com'),
    }
    
    # Render HTML template
    html_content = render_to_string('accounts/emails/welcome.html', context)
    text_content = strip_tags(html_content)
    
    # Send email
    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else None,
            to=[user.email],
        )
        email.attach_alternative(html_content, 'text/html')
        email.send(fail_silently=False)
        return True
    except Exception as e:
        # Log the error but don't raise - user was created successfully
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Failed to send welcome email to {user.email}: {str(e)}')
        return False


def send_password_reset_email(user, temp_password):
    """
    Send password reset email with new temporary password.
    
    Args:
        user: User instance
        temp_password: The new temporary password
    """
    subject = 'Task Manager - Password Reset'
    
    context = {
        'user': user,
        'temp_password': temp_password,
        'login_url': getattr(settings, 'SITE_URL', 'http://localhost:8000') + '/login/',
    }
    
    # Render HTML template
    html_content = render_to_string('accounts/emails/password_reset.html', context)
    text_content = strip_tags(html_content)
    
    # Send email
    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else None,
            to=[user.email],
        )
        email.attach_alternative(html_content, 'text/html')
        email.send(fail_silently=False)
        return True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Failed to send password reset email to {user.email}: {str(e)}')
        return False


def send_lockout_notification(user):
    """
    Send notification when account is locked due to failed login attempts.
    
    Args:
        user: User instance
    """
    subject = 'Task Manager - Account Locked'
    
    lockout_duration = getattr(settings, 'LOCKOUT_DURATION', 15 * 60)
    lockout_minutes = lockout_duration // 60
    
    context = {
        'user': user,
        'lockout_minutes': lockout_minutes,
        'support_email': getattr(settings, 'SUPPORT_EMAIL', 'admin@centuryextrusions.com'),
    }
    
    # Render HTML template
    html_content = render_to_string('accounts/emails/account_locked.html', context)
    text_content = strip_tags(html_content)
    
    # Send email
    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else None,
            to=[user.email],
        )
        email.attach_alternative(html_content, 'text/html')
        email.send(fail_silently=False)
        return True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Failed to send lockout notification to {user.email}: {str(e)}')
        return False


def invalidate_user_sessions(user, exclude_session_key=None):
    """
    Invalidate all sessions for a user (e.g., after password change).
    
    Args:
        user: User instance
        exclude_session_key: Optional session key to keep (current session)
    """
    from django.contrib.sessions.models import Session
    from django.utils import timezone
    
    # Get all active sessions
    active_sessions = Session.objects.filter(expire_date__gt=timezone.now())
    
    for session in active_sessions:
        session_data = session.get_decoded()
        if session_data.get('_auth_user_id') == str(user.pk):
            if exclude_session_key and session.session_key == exclude_session_key:
                continue
            session.delete()


def get_user_by_email(email):
    """
    Get user by email (case-insensitive).
    
    Args:
        email: Email address to search
    
    Returns:
        User instance or None
    """
    try:
        return User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        return None


def create_user(email, first_name, last_name, role='employee', department=None, send_email=True):
    """
    Create a new user with a temporary password.
    
    Args:
        email: User's email address
        first_name: User's first name
        last_name: User's last name
        role: User's role (default: employee)
        department: Department instance (optional)
        send_email: Whether to send welcome email
    
    Returns:
        tuple: (User instance, temporary password)
    """
    # Generate temporary password
    temp_password = generate_temp_password()
    
    # Create user
    user = User.objects.create_user(
        email=email.lower().strip(),
        password=temp_password,
        first_name=first_name,
        last_name=last_name,
        role=role,
        department=department,
        must_change_password=True,
    )
    
    # Send welcome email
    if send_email:
        send_welcome_email(user, temp_password)
    
    return user, temp_password


def deactivate_user(user, deactivated_by=None):
    """
    Deactivate a user account.
    
    Args:
        user: User instance to deactivate
        deactivated_by: User who performed the deactivation (for logging)
    
    Returns:
        dict: Summary of pending tasks that need attention
    """
    from apps.tasks.models import Task
    
    # Get pending tasks summary before deactivation
    pending_assigned = Task.objects.filter(
        assignee=user,
        status__in=['pending', 'in_progress']
    ).count()
    
    pending_created = Task.objects.filter(
        created_by=user,
        status__in=['pending', 'in_progress']
    ).exclude(assignee=user).count()
    
    # Deactivate user
    user.is_active = False
    user.save()
    
    # Invalidate all sessions
    invalidate_user_sessions(user)
    
    return {
        'user': user,
        'pending_tasks_assigned': pending_assigned,
        'pending_tasks_created': pending_created,
    }
