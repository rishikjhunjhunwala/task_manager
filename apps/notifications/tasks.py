"""
Scheduled tasks for notifications app.

Background jobs for:
- Deadline reminders (hourly)
- Overdue checks and escalations (daily at 9 AM IST)
- Daily dashboard emails (daily at 8 AM IST)

Will be expanded in Phase 10 (Scheduled Jobs).
"""

from django.utils import timezone
from datetime import timedelta


def check_deadline_reminders():
    """
    Scheduled job to run hourly.
    Sends reminder 24 hours before deadline.
    
    Will be implemented in Phase 10.
    """
    pass


def check_overdue_tasks():
    """
    Scheduled job to run daily at 9:00 AM IST.
    
    Actions:
    - Send daily reminder to assignee + creator
    - 72-hour escalation → Senior Manager 2
    - 120-hour escalation → Senior Manager 1
    
    Will be implemented in Phase 10.
    """
    pass


def send_daily_dashboard_emails():
    """
    Scheduled job to run daily at 8:00 AM IST.
    
    Sends task snapshot to users with pending tasks.
    Users with no pending tasks are skipped.
    
    Will be implemented in Phase 10.
    """
    pass
