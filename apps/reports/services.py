"""
Service layer for reports app.
Will be expanded in Phase 8 (Activity Log & Reports).
"""

from django.db.models import Count, Q
from django.utils import timezone


def get_summary_stats(user, department=None):
    """
    Get summary statistics for tasks.
    
    Returns dict with counts for:
    - pending
    - in_progress
    - completed
    - overdue
    
    Will be implemented in Phase 8.
    """
    pass


def get_user_breakdown(user, department=None):
    """
    Get task counts by user.
    
    Returns queryset with per-user task counts.
    
    Will be implemented in Phase 8.
    """
    pass


def get_overdue_tasks(user, department=None):
    """
    Get list of overdue tasks.
    
    Will be implemented in Phase 8.
    """
    pass


def get_escalated_tasks(user, department=None):
    """
    Get list of escalated tasks (72+ hours overdue).
    
    Will be implemented in Phase 8.
    """
    pass
