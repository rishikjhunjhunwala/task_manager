"""
Service layer for accounts app.

Centralized business logic for:
- Temporary password generation
- Welcome email sending
- Password reset
- Account lockout notifications
- Session management
"""

import secrets
import string
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.contrib.sessions.models import Session


def generate_temp_password(length=16):
    """
    Generate a secure temporary password meeting complexity requirements.
    
    Requirements:
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 digit
    - At least 1 special character
    - Minimum 12 characters (we use 16 for extra security)
    
    Returns:
        str: A secure temporary password
    """
    # Define character sets
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special = '!@#$%^&*()_+-=[]{}|;:,.?'    

    
    # Ensure at least one of each required type
    password = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(special),
    ]
    
    # Fill remaining length with random characters from all sets
    all_chars = uppercase + lowercase + digits + special
    password.extend(secrets.choice(all_chars) for _ in range(length - 4))
    
    # Shuffle to avoid predictable patterns
    password_list = list(password)
    secrets.SystemRandom().shuffle(password_list)
    
    return ''.join(password_list)


def send_welcome_email(user, temp_password):
    """
    Send welcome email to newly created user with credentials.
    
    Args:
        user: User instance
        temp_password: The temporary password to include
    
    Returns:
        bool: True if email sent successfully
    """
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    
    context = {
        'user': user,
        'temp_password': temp_password,
        'login_url': f'{site_url}/login/',
        'site_url': site_url,
        'support_email': getattr(settings, 'SUPPORT_EMAIL', 'support@centuryextrusions.com'),
    }
    
    subject = 'Welcome to Task Manager - Your Account Details'
    
    # Render HTML and plain text versions
    html_content = render_to_string('accounts/emails/welcome.html', context)
    text_content = render_to_string('accounts/emails/welcome.txt', context)
    
    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@centuryextrusions.com'),
            to=[user.email],
        )
        email.attach_alternative(html_content, 'text/html')
        email.send()
        return True
    except Exception as e:
        # Log the error but don't raise - user is already created
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Failed to send welcome email to {user.email}: {e}')
        return False


def send_password_reset_email(user, temp_password):
    """
    Send password reset email with new temporary password.
    
    Args:
        user: User instance
        temp_password: The new temporary password
    
    Returns:
        bool: True if email sent successfully
    """
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    
    context = {
        'user': user,
        'temp_password': temp_password,
        'login_url': f'{site_url}/login/',
        'site_url': site_url,
        'support_email': getattr(settings, 'SUPPORT_EMAIL', 'support@centuryextrusions.com'),
    }
    
    subject = 'Task Manager - Your Password Has Been Reset'
    
    html_content = render_to_string('accounts/emails/password_reset.html', context)
    text_content = render_to_string('accounts/emails/password_reset.txt', context)
    
    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@centuryextrusions.com'),
            to=[user.email],
        )
        email.attach_alternative(html_content, 'text/html')
        email.send()
        return True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Failed to send password reset email to {user.email}: {e}')
        return False


def send_lockout_notification(user):
    """
    Send notification when account is locked due to failed login attempts.
    
    Args:
        user: User instance
    
    Returns:
        bool: True if email sent successfully
    """
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    lockout_minutes = getattr(settings, 'LOCKOUT_DURATION', 900) // 60
    
    context = {
        'user': user,
        'lockout_minutes': lockout_minutes,
        'locked_until': user.locked_until,
        'site_url': site_url,
        'support_email': getattr(settings, 'SUPPORT_EMAIL', 'support@centuryextrusions.com'),
    }
    
    subject = 'Task Manager - Account Temporarily Locked'
    
    html_content = render_to_string('accounts/emails/account_locked.html', context)
    text_content = render_to_string('accounts/emails/account_locked.txt', context)
    
    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@centuryextrusions.com'),
            to=[user.email],
        )
        email.attach_alternative(html_content, 'text/html')
        email.send()
        return True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Failed to send lockout notification to {user.email}: {e}')
        return False


def invalidate_user_sessions(user):
    """
    Invalidate all sessions for a user.
    Called when password is changed or user is deactivated.
    
    Args:
        user: User instance
    
    Returns:
        int: Number of sessions invalidated
    """
    count = 0
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        try:
            session_data = session.get_decoded()
            if session_data.get('_auth_user_id') == str(user.pk):
                session.delete()
                count += 1
        except Exception:
            # Session decode failed, skip it
            pass
    return count


def create_user_with_temp_password(email, first_name, last_name, role, department=None):
    """
    Create a new user with a temporary password.
    Sends welcome email automatically.
    
    Args:
        email: User's email address
        first_name: User's first name
        last_name: User's last name
        role: User's role
        department: User's department (optional)
    
    Returns:
        tuple: (user, temp_password, email_sent)
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    temp_password = generate_temp_password()
    
    user = User.objects.create_user(
        email=email,
        password=temp_password,
        first_name=first_name,
        last_name=last_name,
        role=role,
        department=department,
        must_change_password=True,
    )
    
    email_sent = send_welcome_email(user, temp_password)
    
    return user, temp_password, email_sent


def reset_user_password(user):
    """
    Reset a user's password and send notification.
    Used by admin for password reset functionality.
    
    Args:
        user: User instance
    
    Returns:
        tuple: (temp_password, email_sent)
    """
    temp_password = generate_temp_password()
    
    # Set new password
    user.set_password(temp_password)
    user.must_change_password = True
    user.password_changed_at = None  # Force password change
    user.save(update_fields=['password', 'must_change_password', 'password_changed_at'])
    
    # Invalidate all existing sessions
    invalidate_user_sessions(user)
    
    # Send email
    email_sent = send_password_reset_email(user, temp_password)
    
    return temp_password, email_sent


def unlock_user_account(user):
    """
    Unlock a user's account manually.
    
    Args:
        user: User instance
    
    Returns:
        bool: True if account was unlocked
    """
    if user.is_locked():
        user.unlock_account()
        return True
    return False


def deactivate_user(user):
    """
    Deactivate a user account.
    Invalidates all sessions.
    
    Args:
        user: User instance
    
    Returns:
        int: Number of sessions invalidated
    """
    user.is_active = False
    user.save(update_fields=['is_active'])
    
    # Invalidate all sessions
    return invalidate_user_sessions(user)


def get_user_task_summary(user):
    """
    Get summary of tasks associated with a user.
    Used to show warnings when deactivating users.
    
    Args:
        user: User instance
    
    Returns:
        dict: Task counts
    """
    from apps.tasks.models import Task
    
    # Tasks assigned to this user
    assigned_tasks = Task.objects.filter(
        assignee=user,
        status__in=['pending', 'in_progress']
    )
    
    # Tasks created by this user
    created_tasks = Task.objects.filter(
        created_by=user,
        status__in=['pending', 'in_progress']
    ).exclude(assignee=user)  # Exclude personal tasks
    
    return {
        'assigned_pending': assigned_tasks.filter(status='pending').count(),
        'assigned_in_progress': assigned_tasks.filter(status='in_progress').count(),
        'assigned_total': assigned_tasks.count(),
        'created_pending': created_tasks.filter(status='pending').count(),
        'created_in_progress': created_tasks.filter(status='in_progress').count(),
        'created_total': created_tasks.count(),
        'has_active_tasks': assigned_tasks.exists() or created_tasks.exists(),
    }
