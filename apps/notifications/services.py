"""
Service layer for notifications app.

Email sending functions for task lifecycle events.
Will be expanded in Phase 9 (Email Notifications).
"""

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings


def send_notification_email(to_email, subject, template_name, context, from_email=None):
    """
    Generic email sending function with HTML/text templates.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        template_name: Base template name (without extension)
        context: Template context dict
        from_email: Sender email (defaults to user's own email)
    
    Will be implemented in Phase 9.
    """
    pass


def notify_task_assigned(task):
    """
    Send notification when a task is assigned.
    Only for delegated tasks (assignee != creator).
    
    Will be implemented in Phase 9.
    """
    pass


def notify_task_completed(task):
    """
    Send notification to creator when a delegated task is completed.
    
    Will be implemented in Phase 9.
    """
    pass


def notify_task_verified(task):
    """
    Send notification to assignee when task is verified.
    
    Will be implemented in Phase 9.
    """
    pass


def notify_task_cancelled(task, reason=None):
    """
    Send notification to assignee when task is cancelled.
    
    Will be implemented in Phase 9.
    """
    pass


def notify_task_reassigned(task, new_assignee):
    """
    Send notification to new assignee when task is reassigned.
    Note: Old assignee is NOT notified.
    
    Will be implemented in Phase 9.
    """
    pass


def send_deadline_reminder(task):
    """
    Send 24-hour deadline reminder to assignee.
    
    Will be implemented in Phase 9.
    """
    pass


def send_overdue_reminder(task):
    """
    Send daily overdue reminder to assignee and creator.
    
    Will be implemented in Phase 9.
    """
    pass


def send_escalation_email(task, level):
    """
    Send escalation notification.
    Level 1: 72 hours → Senior Manager 2
    Level 2: 120 hours → Senior Manager 1
    
    Will be implemented in Phase 9.
    """
    pass


def send_daily_dashboard_email(user, my_tasks, assigned_tasks):
    """
    Send daily task snapshot email.
    
    Will be implemented in Phase 10.
    """
    pass
