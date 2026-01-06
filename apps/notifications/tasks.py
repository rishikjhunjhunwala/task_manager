"""
Scheduled Tasks for Notifications.

This module contains all scheduled/background tasks for the notification system.
These functions are designed to be called by Django-Q2 on a schedule.

Phase 10B: check_deadline_reminders() - Hourly check for 24-hour deadline reminders
Phase 10C: check_overdue_tasks() - Daily overdue reminders and escalation logic
Phase 10D: send_daily_dashboard_emails() - Daily dashboard summary for all users

Usage (Django-Q2):
    These functions are scheduled via management command in Phase 10E.
    For manual testing, use Django shell:
    
    >>> from apps.notifications.tasks import send_daily_dashboard_emails
    >>> stats = send_daily_dashboard_emails()
    >>> print(stats)
"""

import logging
from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import User
from apps.tasks.models import Task
from apps.notifications.services import (
    notify_deadline_reminder,
    notify_overdue,
    notify_escalation_sm2,
    notify_escalation_sm1,
    send_dashboard_email,
)

# Logger for scheduled task activities
logger = logging.getLogger(__name__)


def check_deadline_reminders():
    """
    Check for tasks with deadlines approaching in 23-25 hours and send reminders.
    
    This function is designed to run hourly. The 23-25 hour window ensures
    that tasks due "tomorrow" are caught even with slight timing variations
    in when the job runs.
    
    Business Rules:
        - Only pending/in_progress tasks are checked
        - Only tasks with a deadline are checked
        - Each task only gets ONE reminder (deadline_reminder_sent flag)
        - Time is calculated in IST (via timezone.now())
    
    Returns:
        int: Count of reminders successfully sent
    
    Example:
        >>> from apps.notifications.tasks import check_deadline_reminders
        >>> count = check_deadline_reminders()
        >>> print(f"Sent {count} reminder(s)")
    """
    now = timezone.now()
    
    # Define the time window: 23-25 hours from now
    window_start = now + timedelta(hours=23)
    window_end = now + timedelta(hours=25)
    
    logger.info(
        f"Checking for deadline reminders. Window: {window_start} to {window_end}"
    )
    
    # Query tasks that match all criteria
    tasks = Task.objects.filter(
        status__in=['pending', 'in_progress'],
        deadline__isnull=False,
        deadline__gte=window_start,
        deadline__lte=window_end,
        deadline_reminder_sent=False,
    ).select_related('assignee', 'created_by')
    
    reminders_sent = 0
    
    for task in tasks:
        try:
            # Send the reminder using existing notification service
            success = notify_deadline_reminder(task)
            
            if success:
                # Mark task as reminded to prevent duplicate emails
                task.deadline_reminder_sent = True
                task.save(update_fields=['deadline_reminder_sent'])
                reminders_sent += 1
                
                logger.info(
                    f"Deadline reminder sent for task {task.reference_number} "
                    f"to {task.assignee.email}"
                )
            else:
                logger.warning(
                    f"Failed to send deadline reminder for task {task.reference_number}"
                )
                
        except Exception as e:
            logger.error(
                f"Error sending deadline reminder for task {task.reference_number}: {e}"
            )
    
    logger.info(f"Deadline reminder check complete. Sent {reminders_sent} reminder(s)")
    return reminders_sent


def check_overdue_tasks():
    """
    Check for overdue tasks and send reminders/escalations as needed.
    
    This function is designed to run daily at 9:00 AM IST. It handles:
    1. Daily overdue reminders to assignee AND creator
    2. 72-hour escalation to Senior Manager 2 (one-time)
    3. 120-hour escalation to Senior Manager 1 (one-time)
    
    Business Rules:
        - Only pending/in_progress tasks are checked
        - Overdue = deadline < now AND deadline is not NULL
        - First reminder has different tone (explains escalation timeline)
        - 72h escalation goes to ALL active SM2 users
        - 120h escalation goes to ALL active SM1 users
        - Escalations are one-time only (tracked by timestamp fields)
    
    Returns:
        dict: Statistics about what was processed:
            - reminders: Count of overdue reminders sent
            - sm2_escalations: Count of tasks escalated to SM2
            - sm1_escalations: Count of tasks escalated to SM1
    
    Example:
        >>> from apps.notifications.tasks import check_overdue_tasks
        >>> stats = check_overdue_tasks()
        >>> print(stats)
        {'reminders': 5, 'sm2_escalations': 2, 'sm1_escalations': 1}
    """
    now = timezone.now()
    
    logger.info(f"Starting overdue task check at {now}")
    
    # Statistics tracking
    stats = {
        'reminders': 0,
        'sm2_escalations': 0,
        'sm1_escalations': 0,
    }
    
    # Query all overdue tasks
    overdue_tasks = Task.objects.filter(
        status__in=['pending', 'in_progress'],
        deadline__isnull=False,
        deadline__lt=now,  # Past deadline
    ).select_related('assignee', 'created_by')
    
    logger.info(f"Found {overdue_tasks.count()} overdue task(s)")
    
    for task in overdue_tasks:
        try:
            # Calculate hours overdue
            hours_overdue = (now - task.deadline).total_seconds() / 3600
            
            logger.debug(
                f"Task {task.reference_number}: {hours_overdue:.1f} hours overdue"
            )
            
            # --- Daily Overdue Reminder ---
            is_first_reminder = not task.first_overdue_email_sent
            
            success = notify_overdue(task, is_first_reminder=is_first_reminder)
            
            if success:
                stats['reminders'] += 1
                
                # Mark first reminder as sent
                if is_first_reminder:
                    task.first_overdue_email_sent = True
                    task.save(update_fields=['first_overdue_email_sent'])
                
                logger.info(
                    f"Overdue reminder sent for task {task.reference_number} "
                    f"({'first' if is_first_reminder else 'follow-up'})"
                )
            
            # --- 72-Hour Escalation to SM2 ---
            if hours_overdue >= 72 and task.escalated_to_sm2_at is None:
                escalation_success = notify_escalation_sm2(task)
                
                if escalation_success:
                    task.escalated_to_sm2_at = now
                    task.save(update_fields=['escalated_to_sm2_at'])
                    stats['sm2_escalations'] += 1
                    
                    logger.warning(
                        f"72-hour escalation triggered for task {task.reference_number} "
                        f"- notified SM2 users"
                    )
            
            # --- 120-Hour Escalation to SM1 ---
            if hours_overdue >= 120 and task.escalated_to_sm1_at is None:
                escalation_success = notify_escalation_sm1(task)
                
                if escalation_success:
                    task.escalated_to_sm1_at = now
                    task.save(update_fields=['escalated_to_sm1_at'])
                    stats['sm1_escalations'] += 1
                    
                    logger.critical(
                        f"120-hour CRITICAL escalation triggered for task "
                        f"{task.reference_number} - notified SM1 users"
                    )
                    
        except Exception as e:
            logger.error(
                f"Error processing overdue task {task.reference_number}: {e}"
            )
    
    logger.info(
        f"Overdue check complete. Stats: {stats['reminders']} reminders, "
        f"{stats['sm2_escalations']} SM2 escalations, "
        f"{stats['sm1_escalations']} SM1 escalations"
    )
    
    return stats


def send_daily_dashboard_emails():
    """
    Send daily dashboard summary emails to all active users with pending tasks.
    
    This function is designed to run daily at 8:00 AM IST (including weekends).
    It provides each user with a personalized summary of:
    1. Tasks assigned TO them (pending + in_progress)
    2. Tasks they created FOR others (pending + in_progress, assignee != creator)
    
    Business Rules:
        - Only active users receive the email
        - Users with NO pending tasks (in either category) are skipped
        - Only pending and in_progress tasks are included
        - Overdue tasks are highlighted with visual indicators
        - Email includes counts, task lists, and a link to the dashboard
    
    Returns:
        dict: Statistics about what was processed:
            - emails_sent: Count of dashboard emails sent
            - users_skipped: Count of users skipped (no tasks)
            - users_processed: Total active users checked
    
    Example:
        >>> from apps.notifications.tasks import send_daily_dashboard_emails
        >>> stats = send_daily_dashboard_emails()
        >>> print(stats)
        {'emails_sent': 15, 'users_skipped': 5, 'users_processed': 20}
    """
    now = timezone.now()
    today = now.date()
    
    logger.info(f"Starting daily dashboard emails at {now}")
    
    # Statistics tracking
    stats = {
        'emails_sent': 0,
        'users_skipped': 0,
        'users_processed': 0,
    }
    
    # Get all active users
    active_users = User.objects.filter(is_active=True)
    
    logger.info(f"Processing {active_users.count()} active user(s)")
    
    for user in active_users:
        stats['users_processed'] += 1
        
        try:
            # --- Get tasks assigned TO this user ---
            assigned_tasks = Task.objects.filter(
                assignee=user,
                status__in=['pending', 'in_progress'],
            ).select_related('created_by').order_by('deadline', '-priority')
            
            # --- Get tasks this user created FOR others ---
            # (delegated tasks where assignee is NOT the creator)
            created_tasks = Task.objects.filter(
                created_by=user,
                status__in=['pending', 'in_progress'],
            ).exclude(
                assignee=user  # Exclude personal tasks (self-assigned)
            ).select_related('assignee').order_by('deadline', '-priority')
            
            # --- Skip users with no tasks in either category ---
            if not assigned_tasks.exists() and not created_tasks.exists():
                stats['users_skipped'] += 1
                logger.debug(f"Skipping user {user.email} - no pending tasks")
                continue
            
            # --- Send dashboard email ---
            success = send_dashboard_email(
                user=user,
                assigned_tasks=assigned_tasks,
                created_tasks=created_tasks,
            )
            
            if success:
                stats['emails_sent'] += 1
                logger.info(
                    f"Dashboard email sent to {user.email} "
                    f"(assigned: {assigned_tasks.count()}, created: {created_tasks.count()})"
                )
            else:
                logger.warning(f"Failed to send dashboard email to {user.email}")
                
        except Exception as e:
            logger.error(f"Error processing dashboard for user {user.email}: {e}")
    
    logger.info(
        f"Daily dashboard complete. Stats: {stats['emails_sent']} sent, "
        f"{stats['users_skipped']} skipped, {stats['users_processed']} processed"
    )
    
    return stats