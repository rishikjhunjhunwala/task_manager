"""
Views for activity_log app.

Provides admin-only access to the activity log with:
- Filtering by task, user, action type, date range
- Pagination (50 records per page)
- Default sort: newest first (by created_at descending)
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponseForbidden

from .models import TaskActivity
from .filters import ActivityFilter


def is_admin(user):
    """
    Check if user is an admin.
    
    Returns True only for users with 'admin' role.
    """
    return user.is_authenticated and user.role == 'admin'


@login_required
def activity_log_view(request):
    """
    Activity log view (Admin only).
    
    Displays a paginated, filterable list of all task activities.
    
    Business Rules:
    - Admin-only access (returns 403 for non-admin users)
    - Default sort: newest first (by created_at descending)
    - Pagination: 50 records per page
    
    Filters available:
    - task: Filter by specific task
    - user: Filter by user who performed the action
    - action_type: Filter by action type (created, updated, etc.)
    - date_from: Activities on or after this date
    - date_to: Activities on or before this date
    - search: Search in description, task reference, user name
    
    Context:
    - activities: Page object with filtered activities
    - filter: ActivityFilter instance for form rendering
    - page_obj: Alias for activities (for pagination template)
    - total_count: Total number of records (before pagination)
    - filtered_count: Number of records after filtering (before pagination)
    """
    # Admin-only access check
    if not is_admin(request.user):
        return HttpResponseForbidden(
            render(request, 'errors/403.html', {
                'message': 'Access to the activity log is restricted to administrators only.'
            })
        )
    
    # Base queryset - newest first, with optimized related lookups
    queryset = TaskActivity.objects.select_related(
        'task', 'user'
    ).order_by('-created_at')
    
    # Store total count before filtering
    total_count = queryset.count()
    
    # Apply filters
    activity_filter = ActivityFilter(request.GET, queryset=queryset)
    filtered_queryset = activity_filter.qs
    
    # Store filtered count
    filtered_count = filtered_queryset.count()
    
    # Pagination - 50 records per page
    paginator = Paginator(filtered_queryset, 50)
    page_number = request.GET.get('page', 1)
    
    try:
        activities = paginator.page(page_number)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page
        activities = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page
        activities = paginator.page(paginator.num_pages)
    
    # Build context
    context = {
        'activities': activities,
        'filter': activity_filter,
        'page_obj': activities,  # Alias for pagination template compatibility
        'total_count': total_count,
        'filtered_count': filtered_count,
        'is_filtered': activity_filter.is_filtered,
    }
    
    return render(request, 'activity_log/activity_list.html', context)


@login_required
def activity_log_partial(request):
    """
    Partial view for HTMX updates (Phase 8B).
    
    Returns only the activity list table body for dynamic filtering.
    This will be implemented in Phase 8B when adding HTMX enhancements.
    """
    # For now, redirect to main view
    # Will be updated in Phase 8B
    return activity_log_view(request)