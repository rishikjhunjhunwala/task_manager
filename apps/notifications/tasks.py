"""
Scheduled tasks for notifications app.

Background jobs for:
- Deadline reminders (hourly) - Phase 10B
- Overdue checks and escalations (daily at 9 AM IST) - Phase 10C
- Daily dashboard emails (daily at 8 AM IST) - Phase 10D

Uses Django-Q2 for task scheduling and execution.
"""

import logging
from datetime import timedelta

from django.utils import timezone

from apps.tasks.models import Task
from apps.notifications.services import notify_deadline_reminder

# Configure logger for this module
logger = logging.getLogger(__name__)


def check_deadline_reminders():
    """
    Scheduled job to run hourly.
    Sends reminder emails for tasks due approximately 24 hours from now.
    
    Business Logic:
    - Time window: 23-25 hours from current time
    - This 2-hour window ensures tasks aren't missed if job runs
      slightly early or late
    - Only processes tasks with status 'pending' or 'in_progress'
    - Only processes tasks with a deadline set
    - Only processes tasks where deadline_reminder_sent = False
    - Sets deadline_reminder_sent = True after successful send
    
    Returns:
        int: Number of reminder emails successfully sent
    """
    # Get current time (timezone-aware, respects TIME_ZONE in settings)
    now = timezone.now()
    
    # Calculate the time window: 23-25 hours from now
    # This catches tasks with deadlines approximately 24 hours away
    window_start = now + timedelta(hours=23)
    window_end = now + timedelta(hours=25)
    
    logger.info(
        f"Checking deadline reminders: window {window_start} to {window_end}"
    )
    
    # Query tasks that need deadline reminders
    # Conditions:
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
    
    Actions:
    - Send daily reminder to assignee + creator for overdue tasks
    - 72-hour escalation → Email all Senior Manager 2 users
    - 120-hour escalation → Email all Senior Manager 1 users
    
    Will be implemented in Phase 10C.
    """
    pass


def send_daily_dashboard_emails():
    """
    Scheduled job to run daily at 8:00 AM IST.
    
    Sends task snapshot email to users with pending tasks.
    Users with no pending tasks are skipped.
    
    Will be implemented in Phase 10D.
    """
    pass