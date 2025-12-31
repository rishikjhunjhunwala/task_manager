"""
Context processors for tasks app.

Provides task counts and permission flags for navigation badges.
"""

from django.db.models import Q

def user_permissions(request):
    """
    Context processor to provide user permission flags for templates.
    """
    context = {
        'can_assign_to_anyone': False,
        'can_assign_in_department': False,
        'can_view_all_tasks': False,
        'can_view_department_tasks': False,
        'is_admin': False,
        'is_manager_or_above': False,
    }
    
    if not request.user.is_authenticated:
        return context
    
    user = request.user
    context['can_assign_to_anyone'] = user.can_assign_to_anyone()
    context['can_assign_in_department'] = user.can_assign_in_department()
    context['can_view_all_tasks'] = user.can_view_all_tasks()
    context['can_view_department_tasks'] = user.can_view_department_tasks()
    context['is_admin'] = user.is_admin()
    context['is_manager_or_above'] = user.role in ['admin', 'senior_manager_1', 'senior_manager_2', 'manager']
    
    return context


def task_counts(request):
    """
    Context processor to provide task counts for navigation badges.
    
    Returns:
        dict with:
        - pending_task_count: Tasks assigned to current user (pending/in_progress)
        - overdue_task_count: Overdue tasks assigned to current user
        - assigned_by_me_pending: Tasks I assigned that are pending
        - can_view_reports: Whether user can access reports
        - can_view_activity_log: Whether user can access activity log
    """
    context = {
        'pending_task_count': 0,
        'overdue_task_count': 0,
        'assigned_by_me_pending': 0,
        'can_view_reports': False,
        'can_view_activity_log': False,
    }
    
    if not request.user.is_authenticated:
        return context
    
    from django.utils import timezone
    from apps.tasks.models import Task
    
    user = request.user
    now = timezone.now()
    
    # Tasks assigned to current user (pending or in_progress)
    my_tasks = Task.objects.filter(
        assignee=user,
        status__in=['pending', 'in_progress']
    )
    context['pending_task_count'] = my_tasks.count()
    
    # Overdue tasks assigned to me
    overdue_tasks = my_tasks.filter(
        deadline__lt=now,
        deadline__isnull=False
    )
    context['overdue_task_count'] = overdue_tasks.count()
    
    # Tasks I assigned to others that are pending
    assigned_by_me = Task.objects.filter(
        created_by=user,
        status__in=['pending', 'in_progress']
    ).exclude(assignee=user)  # Exclude personal tasks
    context['assigned_by_me_pending'] = assigned_by_me.count()
    
    # Permission flags for navigation
    role = user.role
    context['can_view_reports'] = role in ['admin', 'senior_manager_1', 'senior_manager_2', 'manager']
    context['can_view_activity_log'] = role == 'admin'
    
    return context

"""
Phase 6D: Updated Context Processors
Replace or update your apps/tasks/context_processors.py with this version.

Adds:
- overdue_task_count: For management overview navigation badge (SM+ only)
"""

from django.utils import timezone


def task_counts(request):
    """
    Add task counts to template context for navigation badges.
    
    Returns:
        - pending_task_count: Pending tasks assigned to current user
        - overdue_task_count: Overdue tasks count (SM+ only, for overview badge)
    """
    context = {
        'pending_task_count': 0,
        'overdue_task_count': 0,
    }
    
    if not request.user.is_authenticated:
        return context
    
    from apps.tasks.models import Task
    
    user = request.user
    now = timezone.now()
    
    # Count pending tasks assigned to user
    context['pending_task_count'] = Task.objects.filter(
        assignee=user,
        status__in=['pending', 'in_progress']
    ).count()
    
    # Overdue count for Senior Managers and Admin only
    if user.role in ['admin', 'senior_manager_1', 'senior_manager_2']:
        context['overdue_task_count'] = Task.objects.filter(
            deadline__lt=now,
            status__in=['pending', 'in_progress']
        ).count()
    
    return context


def user_permissions(request):
    """
    Add user permission flags to template context for navigation visibility.
    
    Returns permission flags based on user role.
    """
    context = {
        'can_view_department_tasks': False,
        'can_view_management_overview': False,
        'can_view_reports': False,
        'can_view_activity_log': False,
        'can_manage_users': False,
    }
    
    if not request.user.is_authenticated:
        return context
    
    user = request.user
    role = user.role
    
    # Manager+ can view department tasks
    if role in ['admin', 'senior_manager_1', 'senior_manager_2', 'manager']:
        context['can_view_department_tasks'] = True
        context['can_view_reports'] = True
    
    # Senior Manager+ can view management overview
    if role in ['admin', 'senior_manager_1', 'senior_manager_2']:
        context['can_view_management_overview'] = True
    
    # Admin only
    if role == 'admin':
        context['can_view_activity_log'] = True
        context['can_manage_users'] = True
    
    return context