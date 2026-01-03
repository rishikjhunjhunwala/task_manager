"""
Service layer for reports app.

Provides data aggregation functions for the reports dashboard.
All functions respect role-based access control:
- Employee: No access (handled at view level)
- Manager: Sees only their department's data
- Senior Manager 1/2: Sees all departments (can filter)
- Admin: Sees all departments (can filter)

Functions:
- get_summary_stats: Task counts by status + overdue count
- get_user_breakdown: Per-user task statistics with pagination
- get_overdue_tasks: List of overdue tasks with hours calculation
- get_escalated_tasks: List of escalated tasks (72h+) with levels
"""

from django.db.models import Count, Q, F, Value, CharField
from django.db.models.functions import Concat
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from apps.tasks.models import Task
from apps.accounts.models import User
from apps.departments.models import Department


def get_user_department_scope(user, department_id=None):
    """
    Determine the department scope for a user's reports.
    
    Args:
        user: The requesting user
        department_id: Optional department filter (for SM/Admin)
        
    Returns:
        tuple: (department_filter, is_all_departments)
        - department_filter: Department instance or None (for all)
        - is_all_departments: Boolean indicating if showing all departments
    """
    # Manager always sees only their department
    if user.role == 'manager':
        return (user.department, False)
    
    # SM/Admin can filter by department or see all
    if user.role in ['admin', 'senior_manager_1', 'senior_manager_2']:
        if department_id:
            try:
                department = Department.objects.get(pk=department_id)
                return (department, False)
            except Department.DoesNotExist:
                pass
        return (None, True)  # All departments
    
    # Employee should not reach here (403 at view level)
    return (None, False)


def get_summary_stats(user, department_id=None):
    """
    Get summary statistics for tasks.
    
    Returns dict with counts for:
    - pending: Tasks with status 'pending'
    - in_progress: Tasks with status 'in_progress'
    - completed: Tasks with status 'completed' or 'verified'
    - overdue: Tasks past deadline AND status in (pending, in_progress)
    
    Args:
        user: The requesting user (determines scope)
        department_id: Optional department filter (for SM/Admin only)
        
    Returns:
        dict: {
            'pending': int,
            'in_progress': int,
            'completed': int,
            'overdue': int,
            'total_active': int,
            'department': Department or None
        }
    """
    department, is_all = get_user_department_scope(user, department_id)
    now = timezone.now()
    
    # Base queryset - exclude cancelled
    base_qs = Task.objects.exclude(status='cancelled')
    
    # Apply department filter
    if department:
        base_qs = base_qs.filter(department=department)
    
    # Get counts by status
    status_counts = base_qs.aggregate(
        pending=Count('pk', filter=Q(status='pending')),
        in_progress=Count('pk', filter=Q(status='in_progress')),
        completed=Count('pk', filter=Q(status='completed')),
        verified=Count('pk', filter=Q(status='verified')),
    )
    
    # Count overdue: deadline passed AND status in (pending, in_progress)
    overdue_count = base_qs.filter(
        deadline__lt=now,
        status__in=['pending', 'in_progress']
    ).count()
    
    return {
        'pending': status_counts['pending'],
        'in_progress': status_counts['in_progress'],
        'completed': status_counts['completed'] + status_counts['verified'],
        'overdue': overdue_count,
        'total_active': status_counts['pending'] + status_counts['in_progress'],
        'department': department,
        'is_all_departments': is_all,
    }


def get_user_breakdown(user, department_id=None, page=1, per_page=25):
    """
    Get task counts broken down by user.
    
    For each user in scope, returns:
    - User info (name, email, department)
    - Count of pending tasks
    - Count of in_progress tasks
    - Count of completed tasks (completed + verified)
    - Count of overdue tasks
    
    Sorted by department name, then user name.
    Paginated: 25 users per page.
    
    Args:
        user: The requesting user (determines scope)
        department_id: Optional department filter (for SM/Admin only)
        page: Page number (default 1)
        per_page: Users per page (default 25)
        
    Returns:
        dict: {
            'users': list of user stat dicts,
            'page_obj': Paginator page object,
            'department': Department or None
        }
    """
    department, is_all = get_user_department_scope(user, department_id)
    now = timezone.now()
    
    # Get users in scope
    users_qs = User.objects.filter(is_active=True).select_related('department')
    
    if department:
        users_qs = users_qs.filter(department=department)
    
    # Order by department name, then user name
    users_qs = users_qs.order_by(
        'department__name',
        'first_name',
        'last_name'
    )
    
    # Annotate with task counts
    users_qs = users_qs.annotate(
        pending_count=Count(
            'assigned_tasks',
            filter=Q(
                assigned_tasks__status='pending'
            ) & ~Q(assigned_tasks__status='cancelled')
        ),
        in_progress_count=Count(
            'assigned_tasks',
            filter=Q(
                assigned_tasks__status='in_progress'
            ) & ~Q(assigned_tasks__status='cancelled')
        ),
        completed_count=Count(
            'assigned_tasks',
            filter=Q(
                assigned_tasks__status__in=['completed', 'verified']
            )
        ),
        overdue_count=Count(
            'assigned_tasks',
            filter=Q(
                assigned_tasks__deadline__lt=now,
                assigned_tasks__status__in=['pending', 'in_progress']
            )
        )
    )
    
    # Paginate
    paginator = Paginator(users_qs, per_page)
    
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    # Build user stats list
    user_stats = []
    for u in page_obj:
        total_tasks = (
            u.pending_count + 
            u.in_progress_count + 
            u.completed_count
        )
        
        user_stats.append({
            'user': u,
            'full_name': u.get_full_name() or u.email,
            'email': u.email,
            'department': u.department,
            'department_name': u.department.name if u.department else 'No Department',
            'pending': u.pending_count,
            'in_progress': u.in_progress_count,
            'completed': u.completed_count,
            'overdue': u.overdue_count,
            'total': total_tasks,
            'completion_rate': (
                (u.completed_count / total_tasks * 100) 
                if total_tasks > 0 else 0
            ),
        })
    
    return {
        'users': user_stats,
        'page_obj': page_obj,
        'department': department,
        'is_all_departments': is_all,
    }


def get_overdue_tasks(user, department_id=None, limit=50):
    """
    Get list of overdue tasks.
    
    Overdue = deadline < now AND status in (pending, in_progress)
    
    Returns tasks with:
    - reference_number, title
    - assignee (user object)
    - department
    - deadline
    - hours_overdue (calculated)
    
    Sorted by deadline ascending (most overdue first).
    
    Args:
        user: The requesting user (determines scope)
        department_id: Optional department filter (for SM/Admin only)
        limit: Maximum number of tasks to return (default 50)
        
    Returns:
        dict: {
            'tasks': list of task dicts,
            'count': total count of overdue tasks,
            'department': Department or None
        }
    """
    department, is_all = get_user_department_scope(user, department_id)
    now = timezone.now()
    
    # Base queryset for overdue tasks
    overdue_qs = Task.objects.filter(
        deadline__lt=now,
        status__in=['pending', 'in_progress']
    ).select_related(
        'assignee',
        'created_by',
        'department'
    ).order_by('deadline')  # Most overdue first (earliest deadline)
    
    # Apply department filter
    if department:
        overdue_qs = overdue_qs.filter(department=department)
    
    # Get total count before limiting
    total_count = overdue_qs.count()
    
    # Apply limit
    tasks_list = overdue_qs[:limit]
    
    # Build task data with hours_overdue calculation
    overdue_tasks = []
    for task in tasks_list:
        # Calculate hours overdue
        if task.deadline:
            delta = now - task.deadline
            hours_overdue = delta.total_seconds() / 3600
        else:
            hours_overdue = 0
        
        overdue_tasks.append({
            'task': task,
            'reference_number': task.reference_number,
            'title': task.title,
            'assignee': task.assignee,
            'assignee_name': task.assignee.get_full_name() or task.assignee.email,
            'created_by': task.created_by,
            'department': task.department,
            'department_name': task.department.name if task.department else 'N/A',
            'deadline': task.deadline,
            'status': task.status,
            'priority': task.priority,
            'hours_overdue': hours_overdue,
            'is_escalated': task.escalated_to_sm2_at is not None,
        })
    
    return {
        'tasks': overdue_tasks,
        'count': total_count,
        'showing': len(overdue_tasks),
        'department': department,
        'is_all_departments': is_all,
    }


def get_escalated_tasks(user, department_id=None, limit=50):
    """
    Get list of escalated tasks (72+ hours overdue).
    
    Escalated = escalated_to_sm2_at IS NOT NULL
    
    Escalation levels:
    - Level 1: Only escalated_to_sm2_at set (72h overdue)
    - Level 2: escalated_to_sm1_at also set (120h overdue)
    
    Returns tasks with:
    - reference_number, title
    - assignee, department
    - deadline
    - escalation_level (1 or 2)
    - escalated_to_sm2_at, escalated_to_sm1_at timestamps
    
    Sorted by escalated_to_sm2_at ascending (oldest escalation first).
    
    Args:
        user: The requesting user (determines scope)
        department_id: Optional department filter (for SM/Admin only)
        limit: Maximum number of tasks to return (default 50)
        
    Returns:
        dict: {
            'tasks': list of task dicts,
            'count': total count,
            'level_1_count': tasks at level 1,
            'level_2_count': tasks at level 2,
            'department': Department or None
        }
    """
    department, is_all = get_user_department_scope(user, department_id)
    now = timezone.now()
    
    # Base queryset - escalated tasks (72h+)
    # Only include tasks that are still active (not completed/verified/cancelled)
    escalated_qs = Task.objects.filter(
        escalated_to_sm2_at__isnull=False,
        status__in=['pending', 'in_progress']
    ).select_related(
        'assignee',
        'created_by',
        'department'
    ).order_by('escalated_to_sm2_at')  # Oldest escalation first
    
    # Apply department filter
    if department:
        escalated_qs = escalated_qs.filter(department=department)
    
    # Get counts
    total_count = escalated_qs.count()
    level_2_count = escalated_qs.filter(escalated_to_sm1_at__isnull=False).count()
    level_1_count = total_count - level_2_count
    
    # Apply limit
    tasks_list = escalated_qs[:limit]
    
    # Build task data
    escalated_tasks = []
    for task in tasks_list:
        # Determine escalation level
        if task.escalated_to_sm1_at:
            escalation_level = 2  # 120h+ overdue
        else:
            escalation_level = 1  # 72h+ overdue
        
        # Calculate hours overdue
        if task.deadline:
            delta = now - task.deadline
            hours_overdue = delta.total_seconds() / 3600
        else:
            hours_overdue = 0
        
        escalated_tasks.append({
            'task': task,
            'reference_number': task.reference_number,
            'title': task.title,
            'assignee': task.assignee,
            'assignee_name': task.assignee.get_full_name() or task.assignee.email,
            'created_by': task.created_by,
            'department': task.department,
            'department_name': task.department.name if task.department else 'N/A',
            'deadline': task.deadline,
            'status': task.status,
            'priority': task.priority,
            'hours_overdue': hours_overdue,
            'escalation_level': escalation_level,
            'escalated_to_sm2_at': task.escalated_to_sm2_at,
            'escalated_to_sm1_at': task.escalated_to_sm1_at,
        })
    
    return {
        'tasks': escalated_tasks,
        'count': total_count,
        'showing': len(escalated_tasks),
        'level_1_count': level_1_count,
        'level_2_count': level_2_count,
        'department': department,
        'is_all_departments': is_all,
    }


def get_departments_for_filter(user):
    """
    Get list of departments for the filter dropdown.
    
    Only returns departments for users who can filter:
    - Admin: All departments
    - Senior Manager 1/2: All departments
    - Manager: None (fixed to their department)
    - Employee: None (no access)
    
    Args:
        user: The requesting user
        
    Returns:
        QuerySet of Department objects or None
    """
    if user.role in ['admin', 'senior_manager_1', 'senior_manager_2']:
        return Department.objects.all().order_by('name')
    return None