"""
Scheduled Tasks for Task Manager Notifications.

This module contains all scheduled task functions that are executed by
Django-Q2. These functions are designed to be idempotent and logged
for debugging and audit purposes.

Phase 10B: check_deadline_reminders - Hourly deadline reminders
Phase 10C: check_overdue_tasks - Daily overdue reminders + escalation

Schedule Configuration:
- Deadline reminders: Hourly (checks for tasks due in 23-25 hours)
- Overdue check: Daily at 9:00 AM IST (sends reminders + escalates)
"""

import logging
from datetime import timedelta

from django.utils import timezone

from apps.tasks.models import Task
from apps.notifications.services import (
    notify_deadline_reminder,
    notify_overdue,
    notify_escalation_sm2,
    notify_escalation_sm1,
)

# Configure logger for scheduled tasks
logger = logging.getLogger(__name__)


def check_deadline_reminders():
    """
    Scheduled job to send deadline reminders for tasks due in ~24 hours.
    
    This function runs hourly and checks for tasks with deadlines
    in the 23-25 hour window. It sends reminders and marks tasks
    to prevent duplicate notifications.
    
    Business Rules:
    - Only tasks in 'pending' or 'in_progress' status
    - Only tasks with deadlines set
    - Only sends if deadline_reminder_sent is False
    - Marks deadline_reminder_sent = True after sending
    
    Returns:
        int: Number of reminders successfully sent
    """
    now = timezone.now()
    
    # Define the 23-25 hour window for upcoming deadlines
    window_start = now + timedelta(hours=23)
    window_end = now + timedelta(hours=25)
    
    logger.info(
        f"Starting deadline reminder check: "
        f"window={window_start.isoformat()} to {window_end.isoformat()}"
    )
    
    # Query tasks that need reminders:
    # 1. Status is 'pending' or 'in_progress' (active tasks only)
    # 2. Deadline is set (not NULL)
    # 3. Deadline falls within our 23-25 hour window
    # 4. Reminder hasn't been sent yet
    tasks_to_remind = Task.objects.filter(
        status__in=['pending', 'in_progress'],
        deadline__isnull=False,
        deadline__gte=window_start,
        deadline__lte=window_end,
        deadline_reminder_sent=False
    ).select_related('assignee', 'created_by')
    
    # Track count of successful reminders
    reminders_sent = 0
    tasks_found = tasks_to_remind.count()
    
    logger.info(f"Found {tasks_found} tasks needing deadline reminders")
    
    # Process each task
    for task in tasks_to_remind:
        try:
            # Call the existing notification service function
            success = notify_deadline_reminder(task)
            
            if success:
                # Mark as sent to prevent duplicate reminders
                task.deadline_reminder_sent = True
                task.save(update_fields=['deadline_reminder_sent'])
                
                reminders_sent += 1
                logger.info(
                    f"Deadline reminder sent: task={task.reference_number}, "
                    f"assignee={task.assignee.email if task.assignee else 'N/A'}, "
                    f"deadline={task.deadline}"
                )
            else:
                # notify_deadline_reminder handles its own logging for failures
                logger.warning(
                    f"Deadline reminder not sent (service returned False): "
                    f"task={task.reference_number}"
                )
                
        except Exception as e:
            # Log error but continue processing other tasks
            logger.error(
                f"Error sending deadline reminder for task "
                f"{task.reference_number}: {str(e)}",
                exc_info=True
            )
    
    logger.info(
        f"Deadline reminder job completed: "
        f"{reminders_sent}/{tasks_found} reminders sent successfully"
    )
    
    return reminders_sent


def check_overdue_tasks():
    """
    Scheduled job to run daily at 9:00 AM IST.
    
    This function performs three key actions for overdue tasks:
    1. Sends daily reminder emails to assignee AND creator
    2. Escalates to Senior Manager 2 (all SM2 users) after 72 hours
    3. Escalates to Senior Manager 1 (all SM1 users) after 120 hours
    
    Business Rules:
    - Only processes tasks in 'pending' or 'in_progress' status
    - Only processes tasks with deadlines that are past due
    - First overdue reminder has different tone (more urgent, explains escalation)
    - Escalations are one-time only (tracked by timestamp fields)
    - Reassignment does NOT reset escalation clock
    
    Task Fields Used:
    - first_overdue_email_sent: Boolean, tracks if first reminder was sent
    - escalated_to_sm2_at: DateTimeField, timestamp of 72h escalation
    - escalated_to_sm1_at: DateTimeField, timestamp of 120h escalation
    
    Returns:
        dict: Statistics with keys:
            - reminders: Number of daily reminders sent
            - sm2_escalations: Number of 72-hour escalations sent
            - sm1_escalations: Number of 120-hour escalations sent
            - tasks_processed: Total overdue tasks processed
    """
    now = timezone.now()
    
    logger.info(f"Starting overdue task check at {now.isoformat()}")
    
    # Initialize statistics
    stats = {
        'reminders': 0,
        'sm2_escalations': 0,
        'sm1_escalations': 0,
        'tasks_processed': 0,
    }
    
    # Query all overdue tasks:
    # 1. Status is 'pending' or 'in_progress' (active tasks only)
    # 2. Deadline is set (not NULL)
    # 3. Deadline is in the past (before now)
    overdue_tasks = Task.objects.filter(
        status__in=['pending', 'in_progress'],
        deadline__isnull=False,
        deadline__lt=now
    ).select_related('assignee', 'created_by', 'department')
    
    tasks_found = overdue_tasks.count()
    logger.info(f"Found {tasks_found} overdue tasks to process")
    
    # Process each overdue task
    for task in overdue_tasks:
        try:
            stats['tasks_processed'] += 1
            
            # Calculate how many hours the task has been overdue
            time_overdue = now - task.deadline
            hours_overdue = time_overdue.total_seconds() / 3600
            
            logger.debug(
                f"Processing overdue task: {task.reference_number}, "
                f"hours_overdue={hours_overdue:.1f}, "
                f"first_email_sent={task.first_overdue_email_sent}, "
                f"sm2_escalated={task.escalated_to_sm2_at is not None}, "
                f"sm1_escalated={task.escalated_to_sm1_at is not None}"
            )
            
            # ------------------------------------------------------------------
            # Step 1: Send daily overdue reminder to assignee + creator
            # ------------------------------------------------------------------
            # Determine if this is the first overdue reminder
            is_first_reminder = not task.first_overdue_email_sent
            
            # Send the overdue reminder (goes to both assignee AND creator)
            reminder_sent = notify_overdue(task, is_first_reminder=is_first_reminder)
            
            if reminder_sent:
                stats['reminders'] += 1
                logger.info(
                    f"Overdue reminder sent: task={task.reference_number}, "
                    f"is_first={is_first_reminder}, hours_overdue={hours_overdue:.1f}"
                )
                
                # Mark first overdue email as sent (if it was the first)
                if is_first_reminder:
                    task.first_overdue_email_sent = True
                    task.save(update_fields=['first_overdue_email_sent'])
                    logger.debug(
                        f"Marked first_overdue_email_sent=True for "
                        f"{task.reference_number}"
                    )
            else:
                logger.warning(
                    f"Overdue reminder not sent (service returned False): "
                    f"task={task.reference_number}"
                )
            
            # ------------------------------------------------------------------
            # Step 2: 72-hour escalation to Senior Manager 2
            # ------------------------------------------------------------------
            # Only escalate if:
            # - Task has been overdue for >= 72 hours
            # - Not already escalated to SM2 (escalated_to_sm2_at is NULL)
            if hours_overdue >= 72 and task.escalated_to_sm2_at is None:
                escalation_sent = notify_escalation_sm2(task)
                
                if escalation_sent:
                    stats['sm2_escalations'] += 1
                    
                    # Record the escalation timestamp
                    task.escalated_to_sm2_at = now
                    task.save(update_fields=['escalated_to_sm2_at'])
                    
                    logger.info(
                        f"72-hour escalation to SM2 sent: "
                        f"task={task.reference_number}, hours_overdue={hours_overdue:.1f}"
                    )
                else:
                    logger.warning(
                        f"72-hour escalation failed (service returned False): "
                        f"task={task.reference_number}"
                    )
            
            # ------------------------------------------------------------------
            # Step 3: 120-hour escalation to Senior Manager 1
            # ------------------------------------------------------------------
            # Only escalate if:
            # - Task has been overdue for >= 120 hours
            # - Not already escalated to SM1 (escalated_to_sm1_at is NULL)
            if hours_overdue >= 120 and task.escalated_to_sm1_at is None:
                escalation_sent = notify_escalation_sm1(task)
                
                if escalation_sent:
                    stats['sm1_escalations'] += 1
                    
                    # Record the escalation timestamp
                    task.escalated_to_sm1_at = now
                    task.save(update_fields=['escalated_to_sm1_at'])
                    
                    logger.info(
                        f"120-hour escalation to SM1 sent: "
                        f"task={task.reference_number}, hours_overdue={hours_overdue:.1f}"
                    )
                else:
                    logger.warning(
                        f"120-hour escalation failed (service returned False): "
                        f"task={task.reference_number}"
                    )
                    
        except Exception as e:
            # Log error but continue processing other tasks
            logger.error(
                f"Error processing overdue task {task.reference_number}: {str(e)}",
                exc_info=True
            )
    
    # Log final statistics
    logger.info(
        f"Overdue task check completed: "
        f"tasks_processed={stats['tasks_processed']}, "
        f"reminders_sent={stats['reminders']}, "
        f"sm2_escalations={stats['sm2_escalations']}, "
        f"sm1_escalations={stats['sm1_escalations']}"
    )
    
    return stats


def send_daily_dashboard_emails():
    """
    Scheduled job to run daily at 8:00 AM IST.
    
    Sends task snapshot email to users with pending tasks.
    Users with no pending tasks are skipped.
    
    Will be implemented in Phase 10D.
    """
    pass