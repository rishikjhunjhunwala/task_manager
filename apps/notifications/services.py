"""
Notification Services for Task Manager.

Phase 9A: Core email sending functionality with HTML and plain text support.
Phase 9B: Task assignment and completion notification functions.
Phase 9C: Task status change notifications (verified, cancelled, reassigned).

This module provides the central email sending functionality for all
notification types in the application. All email notifications should
use the send_notification_email() function for consistency.
...
"""

import logging
from datetime import datetime
from typing import Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils import timezone

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
    return f"{base_url}/tasks/{task.pk}/"


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


def format_datetime_for_email(dt) -> str:
    """
    Format a datetime object for display in emails.
    
    Uses the format: DD MMM YYYY, HH:MM AM/PM (IST)
    
    Args:
        dt: datetime object to format
    
    Returns:
        str: Formatted datetime string or 'No deadline set' if None
    """
    if dt is None:
        return 'No deadline set'
    
    # Ensure datetime is in the correct timezone (IST)
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    
    # Format: "25 Dec 2025, 02:30 PM"
    return dt.strftime('%d %b %Y, %I:%M %p')


def get_priority_display(priority: str) -> dict:
    """
    Get display information for a priority level.
    
    Returns a dictionary with the display name and color for use in templates.
    
    Args:
        priority: Priority code ('low', 'medium', 'high', 'critical')
    
    Returns:
        dict: Contains 'name' and 'color' keys
    """
    priority_map = {
        'low': {'name': 'Low', 'color': '#22c55e'},       # Green
        'medium': {'name': 'Medium', 'color': '#3b82f6'}, # Blue
        'high': {'name': 'High', 'color': '#f97316'},     # Orange
        'critical': {'name': 'Critical', 'color': '#ef4444'},  # Red
    }
    return priority_map.get(priority, {'name': priority.title(), 'color': '#6b7280'})


# =============================================================================
# Task Notification Functions (Phase 9B)
# =============================================================================

def notify_task_assigned(task) -> bool:
    """
    Send notification to assignee when a delegated task is created.
    
    This function sends an email to the task assignee informing them that
    a new task has been assigned to them. It includes task details and
    a link to view the task.
    
    Rules:
    - Only sends for DELEGATED tasks (task.task_type == 'delegated')
    - Skips personal tasks (where assignee == creator)
    - Sender is the task creator's email (not system email)
    - Recipient is the task assignee's email
    
    Args:
        task: Task model instance with the following attributes:
            - task_type: 'personal' or 'delegated'
            - assignee: User assigned to complete the task
            - created_by: User who created/assigned the task
            - title: Task title
            - reference_number: Unique task reference
            - description: Task description
            - priority: Priority level
            - deadline: Due date/time (optional)
    
    Returns:
        bool: True if email was sent successfully, False otherwise
              Returns False without error if task is personal (expected behavior)
    
    Example:
        >>> from apps.tasks.models import Task
        >>> task = Task.objects.get(pk=1)
        >>> notify_task_assigned(task)
        True
    """
    # Rule: Only send for DELEGATED tasks
    # Personal tasks (assignee == creator) don't need notification
    if task.task_type != 'delegated':
        logger.debug(
            f"Skipping assignment notification for personal task: "
            f"{task.reference_number}"
        )
        return False
    
    # Double-check: Skip if assignee is the same as creator
    if task.assignee_id == task.created_by_id:
        logger.debug(
            f"Skipping assignment notification - assignee is creator: "
            f"{task.reference_number}"
        )
        return False
    
    # Validate that we have required user information
    if not task.assignee or not task.assignee.email:
        logger.error(
            f"Cannot send assignment notification - assignee has no email: "
            f"{task.reference_number}"
        )
        return False
    
    if not task.created_by or not task.created_by.email:
        logger.error(
            f"Cannot send assignment notification - creator has no email: "
            f"{task.reference_number}"
        )
        return False
    
    # Build task URL
    task_url = get_task_url(task)
    
    # Format deadline for display
    deadline_formatted = format_datetime_for_email(task.deadline)
    
    # Get priority display info
    priority_info = get_priority_display(task.priority)
    
    # Get creator's department name (if available)
    creator_department = ''
    if hasattr(task.created_by, 'department') and task.created_by.department:
        creator_department = task.created_by.department.name
    
    # Truncate description if too long (keep first 500 chars)
    description_truncated = task.description
    if len(task.description) > 500:
        description_truncated = task.description[:497] + '...'
    
    # Build template context
    context = {
        'task': task,
        'task_url': task_url,
        'creator': task.created_by,
        'creator_name': get_user_display_name(task.created_by),
        'creator_department': creator_department,
        'assignee': task.assignee,
        'assignee_name': get_user_display_name(task.assignee),
        'deadline_formatted': deadline_formatted,
        'priority_info': priority_info,
        'description_truncated': description_truncated,
        'has_deadline': task.deadline is not None,
    }
    
    # Build subject line
    subject = f"[Task Assigned] {task.title} - {task.reference_number}"
    
    # Send the email
    # Sender is the creator's email (the person assigning the task)
    result = send_notification_email(
        to_email=task.assignee.email,
        subject=subject,
        template_name='task_assigned',
        context=context,
    )
    
    if result:
        logger.info(
            f"Task assignment notification sent: "
            f"task={task.reference_number}, to={task.assignee.email}"
        )
    else:
        logger.warning(
            f"Failed to send task assignment notification: "
            f"task={task.reference_number}, to={task.assignee.email}"
        )
    
    return result


def notify_task_completed(task) -> bool:
    """
    Send notification to creator when a delegated task is completed.
    
    This function sends an email to the task creator informing them that
    the assignee has marked the task as complete. It includes a link to
    verify the task.
    
    Rules:
    - Only sends for DELEGATED tasks (task.task_type == 'delegated')
    - Sender is the task assignee's email (the person completing)
    - Recipient is the task creator's email
    - Includes prompt to verify the completed task
    
    Args:
        task: Task model instance with the following attributes:
            - task_type: 'personal' or 'delegated'
            - assignee: User who completed the task
            - created_by: User who created/assigned the task
            - title: Task title
            - reference_number: Unique task reference
            - completed_at: Timestamp when marked complete
    
    Returns:
        bool: True if email was sent successfully, False otherwise
              Returns False without error if task is personal (expected behavior)
    
    Example:
        >>> from apps.tasks.models import Task
        >>> task = Task.objects.filter(status='completed', task_type='delegated').first()
        >>> notify_task_completed(task)
        True
    """
    # Rule: Only send for DELEGATED tasks
    # Personal tasks don't need completion notification to self
    if task.task_type != 'delegated':
        logger.debug(
            f"Skipping completion notification for personal task: "
            f"{task.reference_number}"
        )
        return False
    
    # Double-check: Skip if assignee is the same as creator
    if task.assignee_id == task.created_by_id:
        logger.debug(
            f"Skipping completion notification - assignee is creator: "
            f"{task.reference_number}"
        )
        return False
    
    # Validate that we have required user information
    if not task.created_by or not task.created_by.email:
        logger.error(
            f"Cannot send completion notification - creator has no email: "
            f"{task.reference_number}"
        )
        return False
    
    if not task.assignee or not task.assignee.email:
        logger.error(
            f"Cannot send completion notification - assignee has no email: "
            f"{task.reference_number}"
        )
        return False
    
    # Build task URL
    task_url = get_task_url(task)
    
    # Format completion timestamp
    # Use completed_at if available, otherwise use current time
    completed_at = task.completed_at if task.completed_at else timezone.now()
    completed_at_formatted = format_datetime_for_email(completed_at)
    
    # Build template context
    context = {
        'task': task,
        'task_url': task_url,
        'creator': task.created_by,
        'creator_name': get_user_display_name(task.created_by),
        'assignee': task.assignee,
        'assignee_name': get_user_display_name(task.assignee),
        'completed_at_formatted': completed_at_formatted,
    }
    
    # Build subject line
    subject = f"[Task Completed] {task.title} - {task.reference_number}"
    
    # Send the email
    # Sender is the assignee's email (the person completing the task)
    result = send_notification_email(
        to_email=task.created_by.email,
        subject=subject,
        template_name='task_completed',
        context=context,
    )
    
    if result:
        logger.info(
            f"Task completion notification sent: "
            f"task={task.reference_number}, to={task.created_by.email}"
        )
    else:
        logger.warning(
            f"Failed to send task completion notification: "
            f"task={task.reference_number}, to={task.created_by.email}"
        )
    
    return result

# =============================================================================
# Task Status Change Notification Functions (Phase 9C)
# =============================================================================

def notify_task_verified(task) -> bool:
    """
    Send confirmation to assignee when task is verified by creator.
    
    This function notifies the assignee that the task creator has reviewed
    and verified their completed work. This closes the task lifecycle.
    
    Rules:
    - Only sends for DELEGATED tasks (personal tasks skip verification)
    - Recipient is the task assignee (who did the work)
    - Sender is the default system email
    
    Args:
        task: Task model instance with the following attributes:
            - task_type: 'personal' or 'delegated'
            - assignee: User who completed the task
            - created_by: User who verified the task
            - title: Task title
            - reference_number: Unique task reference
            - verified_at: Timestamp when verified (optional)
    
    Returns:
        bool: True if email was sent successfully, False otherwise
              Returns False without error if task is personal (expected behavior)
    
    Example:
        >>> from apps.tasks.models import Task
        >>> from apps.notifications.services import notify_task_verified
        >>> task = Task.objects.filter(status='verified', task_type='delegated').first()
        >>> notify_task_verified(task)
        True
    """
    # Rule: Only send for DELEGATED tasks
    # Personal tasks don't go through verification workflow
    if task.task_type != 'delegated':
        logger.debug(
            f"Skipping verification notification for personal task: "
            f"{task.reference_number}"
        )
        return False
    
    # Double-check: Skip if assignee is the same as creator
    if task.assignee_id == task.created_by_id:
        logger.debug(
            f"Skipping verification notification - assignee is creator: "
            f"{task.reference_number}"
        )
        return False
    
    # Validate that we have required user information
    if not task.assignee or not task.assignee.email:
        logger.error(
            f"Cannot send verification notification - assignee has no email: "
            f"{task.reference_number}"
        )
        return False
    
    if not task.created_by:
        logger.error(
            f"Cannot send verification notification - creator is missing: "
            f"{task.reference_number}"
        )
        return False
    
    # Build task URL
    task_url = get_task_url(task)
    
    # Format verification timestamp
    # Use verified_at if available, otherwise use current time
    verified_at = getattr(task, 'verified_at', None) or timezone.now()
    verified_at_formatted = format_datetime_for_email(verified_at)
    
    # Build template context
    context = {
        'task': task,
        'task_url': task_url,
        'assignee': task.assignee,
        'assignee_name': get_user_display_name(task.assignee),
        'verified_by': task.created_by,
        'verified_by_name': get_user_display_name(task.created_by),
        'verified_at_formatted': verified_at_formatted,
    }
    
    # Build subject line
    subject = f"[Task Verified] {task.title} - {task.reference_number}"
    
    # Send the email
    # Sender is the default system email (per user's edit request)
    result = send_notification_email(
        to_email=task.assignee.email,
        subject=subject,
        template_name='task_verified',
        context=context,
        # from_email not passed - will use DEFAULT_FROM_EMAIL
    )
    
    if result:
        logger.info(
            f"Task verification notification sent: "
            f"task={task.reference_number}, to={task.assignee.email}"
        )
    else:
        logger.warning(
            f"Failed to send task verification notification: "
            f"task={task.reference_number}, to={task.assignee.email}"
        )
    
    return result


def notify_task_cancelled(task, reason: str, cancelled_by) -> bool:
    """
    Send cancellation notice to assignee with reason.
    
    This function notifies the assignee that their assigned task has been
    cancelled and provides the reason for cancellation.
    
    Rules:
    - Send to assignee (they need to know task is cancelled)
    - Reason is required (no empty cancellations allowed)
    - Sender is the default system email
    - Recipient is the task assignee
    
    Args:
        task: Task model instance with the following attributes:
            - assignee: User assigned to the task
            - title: Task title
            - reference_number: Unique task reference
        reason: Cancellation reason string (required, non-empty)
        cancelled_by: User who cancelled the task
    
    Returns:
        bool: True if email was sent successfully, False otherwise
              Returns False if reason is empty or assignee has no email
    
    Example:
        >>> from apps.tasks.models import Task
        >>> from apps.accounts.models import User
        >>> from apps.notifications.services import notify_task_cancelled
        >>> task = Task.objects.filter(task_type='delegated').first()
        >>> admin = User.objects.filter(role='admin').first()
        >>> notify_task_cancelled(task, "Project requirements changed", admin)
        True
    """
    # Validate reason is provided
    if not reason or not reason.strip():
        logger.error(
            f"Cannot send cancellation notification - reason is empty: "
            f"{task.reference_number}"
        )
        return False
    
    # Validate cancelled_by user
    if not cancelled_by:
        logger.error(
            f"Cannot send cancellation notification - cancelled_by is missing: "
            f"{task.reference_number}"
        )
        return False
    
    # Validate assignee exists and has email
    if not task.assignee or not task.assignee.email:
        logger.error(
            f"Cannot send cancellation notification - assignee has no email: "
            f"{task.reference_number}"
        )
        return False
    
    # Skip notification if assignee is the one cancelling (they already know)
    if task.assignee_id == cancelled_by.pk:
        logger.debug(
            f"Skipping cancellation notification - assignee cancelled own task: "
            f"{task.reference_number}"
        )
        return False
    
    # Build task URL
    task_url = get_task_url(task)
    
    # Get current timestamp for cancellation
    cancelled_at_formatted = format_datetime_for_email(timezone.now())
    
    # Build template context
    context = {
        'task': task,
        'task_url': task_url,
        'assignee': task.assignee,
        'assignee_name': get_user_display_name(task.assignee),
        'cancelled_by': cancelled_by,
        'cancelled_by_name': get_user_display_name(cancelled_by),
        'reason': reason.strip(),
        'cancelled_at_formatted': cancelled_at_formatted,
    }
    
    # Build subject line
    subject = f"[Task Cancelled] {task.title} - {task.reference_number}"
    
    # Send the email
    # Sender is the default system email (per user's edit request)
    result = send_notification_email(
        to_email=task.assignee.email,
        subject=subject,
        template_name='task_cancelled',
        context=context,
        # from_email not passed - will use DEFAULT_FROM_EMAIL
    )
    
    if result:
        logger.info(
            f"Task cancellation notification sent: "
            f"task={task.reference_number}, to={task.assignee.email}, "
            f"reason='{reason[:50]}...'" if len(reason) > 50 else f"reason='{reason}'"
        )
    else:
        logger.warning(
            f"Failed to send task cancellation notification: "
            f"task={task.reference_number}, to={task.assignee.email}"
        )
    
    return result


def notify_task_reassigned(task, new_assignee, reassigned_by) -> bool:
    """
    Send notification to NEW assignee only when task is reassigned.
    
    CRITICAL RULE: Old assignee receives NO notification on reassignment.
    This is explicitly stated in the requirements.
    
    Rules:
    - Only notify the NEW assignee
    - Old assignee receives NO notification (per requirements)
    - Sender is the default system email
    - Recipient is the new assignee's email
    - Deadline does NOT reset on reassignment
    
    Args:
        task: Task model instance (should already be updated with new assignee)
            - title: Task title
            - reference_number: Unique task reference
            - description: Task description
            - priority: Priority level
            - deadline: Due date/time (unchanged by reassignment)
        new_assignee: User model instance - the user now assigned to the task
        reassigned_by: User model instance - the user who performed reassignment
    
    Returns:
        bool: True if email was sent successfully, False otherwise
              Returns False if new_assignee has no email
    
    Example:
        >>> from apps.tasks.models import Task
        >>> from apps.accounts.models import User
        >>> from apps.notifications.services import notify_task_reassigned
        >>> task = Task.objects.filter(task_type='delegated').first()
        >>> new_assignee = User.objects.exclude(pk=task.assignee.pk).first()
        >>> notify_task_reassigned(task, new_assignee, task.created_by)
        True
    
    Note:
        The old assignee is intentionally NOT notified. If business requirements
        change in the future, a separate notify_task_unassigned() function
        should be created rather than modifying this function.
    """
    # Validate new_assignee exists and has email
    if not new_assignee or not new_assignee.email:
        logger.error(
            f"Cannot send reassignment notification - new_assignee has no email: "
            f"{task.reference_number}"
        )
        return False
    
    # Validate reassigned_by user
    if not reassigned_by:
        logger.error(
            f"Cannot send reassignment notification - reassigned_by is missing: "
            f"{task.reference_number}"
        )
        return False
    
    # Skip notification if new assignee is the one reassigning to themselves
    if new_assignee.pk == reassigned_by.pk:
        logger.debug(
            f"Skipping reassignment notification - user assigned to self: "
            f"{task.reference_number}"
        )
        return False
    
    # Build task URL
    task_url = get_task_url(task)
    
    # Format deadline for display (deadline does NOT reset on reassignment)
    deadline_formatted = format_datetime_for_email(task.deadline)
    
    # Get priority display info
    priority_info = get_priority_display(task.priority)
    
    # Get reassigned_by user's department (if available)
    reassigned_by_department = ''
    if hasattr(reassigned_by, 'department') and reassigned_by.department:
        reassigned_by_department = reassigned_by.department.name
    
    # Truncate description if too long (keep first 500 chars)
    description_truncated = task.description
    if len(task.description) > 500:
        description_truncated = task.description[:497] + '...'
    
    # Build template context
    context = {
        'task': task,
        'task_url': task_url,
        'new_assignee': new_assignee,
        'new_assignee_name': get_user_display_name(new_assignee),
        'reassigned_by': reassigned_by,
        'reassigned_by_name': get_user_display_name(reassigned_by),
        'reassigned_by_department': reassigned_by_department,
        'deadline_formatted': deadline_formatted,
        'priority_info': priority_info,
        'description_truncated': description_truncated,
        'has_deadline': task.deadline is not None,
    }
    
    # Build subject line
    # Use "Task Assigned to You" to make it clear this is actionable
    subject = f"[Task Assigned to You] {task.title} - {task.reference_number}"
    
    # Send the email
    # Sender is the default system email (per user's edit request)
    result = send_notification_email(
        to_email=new_assignee.email,
        subject=subject,
        template_name='task_reassigned',
        context=context,
        # from_email not passed - will use DEFAULT_FROM_EMAIL
    )
    
    if result:
        logger.info(
            f"Task reassignment notification sent: "
            f"task={task.reference_number}, to={new_assignee.email}"
        )
    else:
        logger.warning(
            f"Failed to send task reassignment notification: "
            f"task={task.reference_number}, to={new_assignee.email}"
        )
    
    return result

# =============================================================================
# Notification Functions Placeholder (Future Phases)
# =============================================================================
#

# Phase 9D:
# - notify_deadline_reminder(task) -> 24-hour deadline warning
# - notify_overdue(task) -> Daily overdue reminder