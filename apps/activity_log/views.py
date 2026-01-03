"""
Views for activity_log app.
Sub-Phase 8A & 8B: Activity Log with filters and pagination.

Access: Admin only
Pagination: 50 records per page
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.utils import timezone
from datetime import datetime

from .models import TaskActivity
from .filters import ActivityFilter
from apps.tasks.models import Task
from apps.accounts.models import User


def is_admin(user):
    """Check if user is an admin."""
    return user.is_authenticated and user.role == 'admin'


@login_required
@user_passes_test(is_admin, login_url='tasks:dashboard')
def activity_log_view(request):
    """
    Activity log view (Admin only).
    
    Features:
    - Filterable by task, user, action type, date range
    - Paginated at 50 records per page
    - Sorted by most recent first
    """
    # Base queryset with optimized relations
    queryset = TaskActivity.objects.select_related(
        'task', 'user'
    ).order_by('-created_at')
    
    # Apply filters from GET parameters
    task_id = request.GET.get('task')
    user_id = request.GET.get('user')
    action_type = request.GET.get('action_type')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Filter by task
    if task_id:
        queryset = queryset.filter(task_id=task_id)
    
    # Filter by user
    if user_id:
        queryset = queryset.filter(user_id=user_id)
    
    # Filter by action type
    if action_type:
        queryset = queryset.filter(action_type=action_type)
    
    # Filter by date range
    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d')
            # Make timezone aware
            date_from_aware = timezone.make_aware(
                datetime.combine(date_from_parsed.date(), datetime.min.time())
            )
            queryset = queryset.filter(created_at__gte=date_from_aware)
        except ValueError:
            pass  # Invalid date format, ignore filter
    
    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d')
            # Make timezone aware, end of day
            date_to_aware = timezone.make_aware(
                datetime.combine(date_to_parsed.date(), datetime.max.time())
            )
            queryset = queryset.filter(created_at__lte=date_to_aware)
        except ValueError:
            pass  # Invalid date format, ignore filter
    
    # Get total count before pagination
    total_count = queryset.count()
    
    # Pagination - 50 per page
    paginator = Paginator(queryset, 50)
    page = request.GET.get('page', 1)
    
    try:
        activities = paginator.page(page)
    except PageNotAnInteger:
        activities = paginator.page(1)
    except EmptyPage:
        activities = paginator.page(paginator.num_pages)
    
    # Get filter dropdown options
    # Tasks - get distinct tasks that have activities
    tasks_with_activities = Task.objects.filter(
        activities__isnull=False
    ).distinct().order_by('-created_at')[:100]  # Limit for performance
    
    # Users - get distinct users who have performed activities
    users_with_activities = User.objects.filter(
        task_activities__isnull=False
    ).distinct().order_by('first_name', 'last_name')
    
    # Action type choices
    action_choices = TaskActivity.ActionType.choices
    
    context = {
        'activities': activities,
        'total_count': total_count,
        'tasks_list': tasks_with_activities,
        'users_list': users_with_activities,
        'action_choices': action_choices,
    }
    
    return render(request, 'activity_log/activity_list.html', context)