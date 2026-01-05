"""
Notification Services for Task Manager.

Phase 9A: Core email sending functionality with HTML and plain text support.

This module provides the central email sending functionality for all
notification types in the application. All email notifications should
use the send_notification_email() function for consistency.

Usage:
    from apps.notifications.services import send_notification_email
    
    result = send_notification_email(
        to_email='user@example.com',
        subject='Task Assigned',
        template_name='task_assigned',
        context={'task': task_instance}
    )
"""

import logging
from datetime import datetime
from typing import Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

# Logger for email-related activities
logger = logging.getLogger(__name__)


def send_notification_email(
    to_email: str,
    subject: str,
    template_name: str,
    context: dict,
    from_email: Optional[str] = None,
) -> bool:
    """
    Send an email notification with HTML and plain text versions.
    
    This is the core email sending function used by all notification types.
    It loads both HTML (.html) and plain text (.txt) templates, adds common
    context variables, and sends via Django's email system.
    
    Args:
        to_email: Recipient email address
        subject: Email subject line (will be prefixed with app name)
        template_name: Base name of template without extension
                      (e.g., 'task_assigned' loads 'task_assigned.html' and 'task_assigned.txt')
        context: Dictionary of variables to pass to the template
        from_email: Sender's email address. If None, uses DEFAULT_FROM_EMAIL.
                   For task notifications, pass the acting user's email.
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    
    Example:
        >>> send_notification_email(
        ...     to_email='assignee@company.com',
        ...     subject='New Task Assigned to You',
        ...     template_name='task_assigned',
        ...     context={
        ...         'task': task,
        ...         'assignee_name': 'John Doe',
        ...     },
        ...     from_email='creator@company.com'
        ... )
        True
    
    Notes:
        - Template files must exist at:
          templates/notifications/emails/{template_name}.html
          templates/notifications/emails/{template_name}.txt
        - Common context variables are automatically added:
          app_name, app_url, company_name, current_year
        - All errors are logged but don't raise exceptions
    """
    # Validate required parameters
    if not to_email or not to_email.strip():
        logger.error("send_notification_email: to_email is empty")
        return False
    
    if not subject or not subject.strip():
        logger.error("send_notification_email: subject is empty")
        return False
    
    if not template_name or not template_name.strip():
        logger.error("send_notification_email: template_name is empty")
        return False
    
    # Use default sender if none provided
    sender_email = from_email or settings.DEFAULT_FROM_EMAIL
    
    # Build template paths
    template_base = f'notifications/emails/{template_name}'
    html_template = f'{template_base}.html'
    text_template = f'{template_base}.txt'
    
    # Add common context variables available to all email templates
    enriched_context = _build_email_context(context)
    
    try:
        # Render plain text version (required)
        try:
            text_content = render_to_string(text_template, enriched_context)
        except TemplateDoesNotExist:
            logger.error(
                f"Plain text template not found: {text_template}. "
                "Both .html and .txt templates are required."
            )
            return False
        
        # Render HTML version (required)
        try:
            html_content = render_to_string(html_template, enriched_context)
        except TemplateDoesNotExist:
            logger.error(
                f"HTML template not found: {html_template}. "
                "Both .html and .txt templates are required."
            )
            return False
        
        # Format subject with app name prefix for consistency
        formatted_subject = f"[{settings.APP_NAME}] {subject}"
        
        # Create email with both text and HTML versions
        # EmailMultiAlternatives allows attaching HTML as an alternative
        # to the plain text body, ensuring email clients can display
        # whichever format they support
        email = EmailMultiAlternatives(
            subject=formatted_subject,
            body=text_content,  # Plain text body (fallback)
            from_email=sender_email,
            to=[to_email],
        )
        
        # Attach HTML version as an alternative
        email.attach_alternative(html_content, 'text/html')
        
        # Send the email
        # fail_silently=False ensures we catch any sending errors
        email.send(fail_silently=False)
        
        logger.info(
            f"Email sent successfully: "
            f"to={to_email}, subject='{subject}', template={template_name}"
        )
        return True
        
    except Exception as e:
        logger.error(
            f"Failed to send email: to={to_email}, subject='{subject}', "
            f"template={template_name}, error={str(e)}"
        )
        return False


def _build_email_context(context: dict) -> dict:
    """
    Add common context variables to email template context.
    
    These variables are available in all email templates:
    - app_name: Application name (e.g., 'Task Manager')
    - app_url: Base URL of the application
    - company_name: Company name for branding
    - current_year: Current year for copyright notices
    - support_email: Email for user support
    
    Args:
        context: Original context dictionary from caller
    
    Returns:
        dict: Enriched context with common variables added
    """
    common_context = {
        'app_name': getattr(settings, 'APP_NAME', 'Task Manager'),
        'app_url': getattr(settings, 'APP_URL', 'http://localhost:8000'),
        'company_name': getattr(settings, 'COMPANY_NAME', 'Century Extrusions / CNFC India'),
        'current_year': datetime.now().year,
        'support_email': getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@centuryextrusions.com'),
    }
    
    # Merge common context with provided context
    # Provided context takes precedence if there are conflicts
    return {**common_context, **context}


def get_task_url(task) -> str:
    """
    Generate the full URL for a task detail page.
    
    This helper function creates the absolute URL for linking to a task
    in email notifications. It uses the APP_URL setting to build the
    full URL.
    
    Args:
        task: Task model instance with reference_number attribute
    
    Returns:
        str: Full URL to the task detail page
    
    Example:
        >>> get_task_url(task)
        'http://localhost:8000/tasks/TASK-2025-0001/'
    """
    base_url = getattr(settings, 'APP_URL', 'http://localhost:8000')
    # Remove trailing slash from base URL if present
    base_url = base_url.rstrip('/')
    return f"{base_url}/tasks/{task.reference_number}/"


def get_user_display_name(user) -> str:
    """
    Get a display-friendly name for a user.
    
    Returns the full name if available, otherwise the username.
    
    Args:
        user: User model instance
    
    Returns:
        str: User's display name
    """
    if hasattr(user, 'get_full_name'):
        full_name = user.get_full_name()
        if full_name:
            return full_name
    return user.username if hasattr(user, 'username') else str(user)


# =============================================================================
# Notification Functions Placeholder (Phase 9B)
# =============================================================================
# The following notification functions will be implemented in Phase 9B:
#
# - notify_task_assigned(task, assigned_by) -> Notify assignee of new task
# - notify_task_completed(task) -> Notify creator when task completed
# - notify_task_verified(task) -> Notify assignee when task verified
# - notify_task_cancelled(task, reason) -> Notify assignee of cancellation
# - notify_task_reassigned(task, old_assignee) -> Notify new assignee only
# - notify_deadline_reminder(task) -> 24-hour deadline warning
# - notify_overdue(task) -> Daily overdue reminder