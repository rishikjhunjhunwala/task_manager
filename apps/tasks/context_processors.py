"""
Context processors for tasks app.

Provides task-related context variables to all templates:
- task_counts: Badge counts for navigation (pending, overdue)

Usage:
    Add to TEMPLATES['OPTIONS']['context_processors'] in settings:
    'apps.tasks.context_processors.task_counts',
    
    In templates:
    {{ pending_task_count }}
    {{ overdue_task_count }}
    {{ my_tasks_count }}
    {{ assigned_to_me_count }}
    {{ i_assigned_count }}
"""

from django.db.models import Q, Count
from django.utils import timezone


def task_counts(request):
    """
    Provide task counts for navigation badges.
    
    Returns context dict with:
    - pending_task_count: Total pending/in_progress tasks assigned to user
    - overdue_task_count: Tasks past deadline (not completed/verified/cancelled)
    - my_tasks_count: Personal tasks (pending/in_progress)
    - assigned_to_me_count: Delegated tasks assigned to user (pending/in_progress)
    - i_assigned_count: Tasks user assigned to others (pending/in_progress)
    
    Only calculated for authenticated users.
    Returns empty dict for anonymous users.
    """
    # Return empty context for unauthenticated users
    if not request.user.is_authenticated:
        return {
            'pending_task_count': 0,
            'overdue_task_count': 0,
            'my_tasks_count': 0,
            'assigned_to_me_count': 0,
            'i_assigned_count': 0,
        }
    
    # Import here to avoid circular imports
    from apps.tasks.models import Task
    
    user = request.user
    now = timezone.now()
    
    # Active statuses (not completed/verified/cancelled)
    active_statuses = ['pending', 'in_progress']
    
    # ==========================================================================
    # Dashboard Tab Counts
    # ==========================================================================
    
    # My Personal Tasks: Tasks I created for myself
    my_tasks_count = Task.objects.filter(
        assignee=user,
        created_by=user,
        status__in=active_statuses
    ).count()
    
    # Assigned to Me: Delegated tasks where I am the assignee
    assigned_to_me_count = Task.objects.filter(
        assignee=user,
        status__in=active_statuses
    ).exclude(
        created_by=user  # Exclude personal tasks
    ).count()
    
    # I Assigned: Tasks I created for others
    i_assigned_count = Task.objects.filter(
        created_by=user,
        status__in=active_statuses
    ).exclude(
        assignee=user  # Exclude personal tasks
    ).count()
    
    # ==========================================================================
    # Navigation Badge Counts
    # ==========================================================================
    
    # Total pending tasks assigned to user (for main nav badge)
    # This includes both personal and delegated tasks
    pending_task_count = Task.objects.filter(
        assignee=user,
        status__in=active_statuses
    ).count()
    
    # Overdue tasks (for alert badge)
    # Tasks assigned to user that are past deadline
    overdue_task_count = Task.objects.filter(
        assignee=user,
        status__in=active_statuses,
        deadline__lt=now,
        deadline__isnull=False
    ).count()
    
    # ==========================================================================
    # Additional Counts (for managers/admin)
    # ==========================================================================
    
    context = {
        # Navigation badges
        'pending_task_count': pending_task_count,
        'overdue_task_count': overdue_task_count,
        
        # Dashboard tab counts
        'my_tasks_count': my_tasks_count,
        'assigned_to_me_count': assigned_to_me_count,
        'i_assigned_count': i_assigned_count,
    }
    
    # Add department counts for managers
    if user.role in ['manager', 'senior_manager_1', 'senior_manager_2', 'admin']:
        context.update(_get_manager_counts(user, active_statuses, now))
    
    return context


def _get_manager_counts(user, active_statuses, now):
    """
    Get additional task counts for managers and above.
    
    Args:
        user: The current user
        active_statuses: List of active status values
        now: Current datetime
    
    Returns:
        Dict with department-level and organization-level counts
    """
    from apps.tasks.models import Task
    
    counts = {}
    
    # Department tasks count (for managers)
    if user.role == 'manager' and user.department:
        department_pending = Task.objects.filter(
            department=user.department,
            status__in=active_statuses
        ).count()
        
        department_overdue = Task.objects.filter(
            department=user.department,
            status__in=active_statuses,
            deadline__lt=now,
            deadline__isnull=False
        ).count()
        
        counts['department_task_count'] = department_pending
        counts['department_overdue_count'] = department_overdue
    
    # Organization-wide counts (for senior managers and admin)
    if user.role in ['senior_manager_1', 'senior_manager_2', 'admin']:
        org_pending = Task.objects.filter(
            status__in=active_statuses
        ).count()
        
        org_overdue = Task.objects.filter(
            status__in=active_statuses,
            deadline__lt=now,
            deadline__isnull=False
        ).count()
        
        # Escalated tasks (72+ hours overdue)
        escalated_count = Task.objects.filter(
            status__in=active_statuses,
            escalated_to_sm2_at__isnull=False
        ).count()
        
        counts['org_task_count'] = org_pending
        counts['org_overdue_count'] = org_overdue
        counts['escalated_task_count'] = escalated_count
    
    return counts


def user_permissions(request):
    """
    Provide user permission flags for templates.
    
    Returns context dict with boolean flags for common permission checks.
    This avoids repeated permission checks in templates.
    
    Usage in templates:
        {% if can_manage_users %}
        {% if can_view_all_tasks %}
    """
    if not request.user.is_authenticated:
        return {
            'can_manage_users': False,
            'can_view_all_tasks': False,
            'can_view_department_tasks': False,
            'can_view_activity_log': False,
            'can_view_reports': False,
            'is_admin': False,
            'is_senior_manager': False,
            'is_manager': False,
        }
    
    user = request.user
    
    return {
        'can_manage_users': user.can_manage_users() if hasattr(user, 'can_manage_users') else user.role == 'admin',
        'can_view_all_tasks': user.can_view_all_tasks() if hasattr(user, 'can_view_all_tasks') else user.role in ['admin', 'senior_manager_1', 'senior_manager_2'],
        'can_view_department_tasks': user.can_view_department_tasks() if hasattr(user, 'can_view_department_tasks') else user.role == 'manager',
        'can_view_activity_log': user.can_view_activity_log() if hasattr(user, 'can_view_activity_log') else user.role == 'admin',
        'can_view_reports': user.role in ['admin', 'senior_manager_1', 'senior_manager_2', 'manager'],
        'is_admin': user.role == 'admin',
        'is_senior_manager': user.role in ['senior_manager_1', 'senior_manager_2'],
        'is_manager': user.role == 'manager',
    }
