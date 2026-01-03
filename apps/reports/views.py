"""
Views for reports app.

Provides the reports dashboard for managers and above.

Permission Model:
- Employee: NO access (403 Forbidden)
- Manager: Sees ONLY their department's data (no filter dropdown)
- Senior Manager 1 & 2: Sees ALL departments with dropdown filter
- Admin: Sees ALL departments with dropdown filter

Views:
- reports_dashboard: Main reports dashboard with summary stats,
  user breakdown, overdue tasks, and escalated tasks
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.contrib import messages

from .services import (
    get_summary_stats,
    get_user_breakdown,
    get_overdue_tasks,
    get_escalated_tasks,
    get_departments_for_filter,
)


def can_access_reports(user):
    """
    Check if user can access reports.
    
    Returns True for: Admin, Senior Manager 1, Senior Manager 2, Manager
    Returns False for: Employee
    """
    return user.is_authenticated and user.role in [
        'admin', 'senior_manager_1', 'senior_manager_2', 'manager'
    ]


def can_filter_departments(user):
    """
    Check if user can filter by department.
    
    Returns True for: Admin, Senior Manager 1, Senior Manager 2
    Returns False for: Manager (fixed to their department)
    """
    return user.role in ['admin', 'senior_manager_1', 'senior_manager_2']


@login_required
def reports_dashboard(request):
    """
    Reports dashboard view.
    
    Displays:
    - Summary stats (task counts by status, overdue count)
    - User breakdown (per-user task statistics, paginated)
    - Overdue tasks list (tasks past deadline)
    - Escalated tasks list (72h+ overdue)
    
    Access:
    - Employee: 403 Forbidden
    - Manager: Fixed to their department
    - SM/Admin: Can filter by department or view all
    
    Query Parameters:
    - department: Department ID filter (SM/Admin only)
    - user_page: Page number for user breakdown pagination
    """
    user = request.user
    
    # Permission check - Employee gets 403
    if not can_access_reports(user):
        return HttpResponseForbidden(
            render(request, 'reports/forbidden.html', {
                'message': 'You do not have permission to access reports.'
            })
        )
    
    # Get department filter from query params (SM/Admin only)
    department_id = None
    if can_filter_departments(user):
        department_id = request.GET.get('department')
        if department_id:
            try:
                department_id = int(department_id)
            except (ValueError, TypeError):
                department_id = None
    
    # Get page number for user breakdown
    user_page = request.GET.get('user_page', 1)
    try:
        user_page = int(user_page)
    except (ValueError, TypeError):
        user_page = 1
    
    # Call all service functions
    summary_stats = get_summary_stats(user, department_id)
    user_breakdown = get_user_breakdown(user, department_id, page=user_page)
    overdue_tasks = get_overdue_tasks(user, department_id)
    escalated_tasks = get_escalated_tasks(user, department_id)
    
    # Get departments for filter dropdown (SM/Admin only)
    departments = get_departments_for_filter(user)
    
    # Determine current department name for display
    if summary_stats['department']:
        current_department_name = summary_stats['department'].name
    elif summary_stats['is_all_departments']:
        current_department_name = 'All Departments'
    else:
        current_department_name = 'No Department'
    
    # Build context
    context = {
        # Page metadata
        'page_title': 'Reports Dashboard',
        
        # User/permission info
        'can_filter_departments': can_filter_departments(user),
        'departments': departments,
        'selected_department_id': department_id,
        'current_department_name': current_department_name,
        
        # Summary statistics
        'summary': summary_stats,
        
        # User breakdown (paginated)
        'user_breakdown': user_breakdown['users'],
        'user_page_obj': user_breakdown['page_obj'],
        
        # Overdue tasks
        'overdue_tasks': overdue_tasks['tasks'],
        'overdue_count': overdue_tasks['count'],
        'overdue_showing': overdue_tasks['showing'],
        
        # Escalated tasks
        'escalated_tasks': escalated_tasks['tasks'],
        'escalated_count': escalated_tasks['count'],
        'escalated_showing': escalated_tasks['showing'],
        'escalated_level_1_count': escalated_tasks['level_1_count'],
        'escalated_level_2_count': escalated_tasks['level_2_count'],
    }
    
    return render(request, 'reports/dashboard.html', context)