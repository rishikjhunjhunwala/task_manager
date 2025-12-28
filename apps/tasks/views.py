"""
Views for tasks app.

Includes:
- Dashboard with tabs (My Personal, Assigned to Me, I Assigned)
- Task CRUD operations
- Task list with filtering and sorting
- Status changes (form and HTMX quick change)
- Comments and attachments
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden, FileResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count
from django.utils import timezone

from .models import Task, Comment, Attachment
from .forms import TaskForm, CommentForm, AttachmentForm, TaskStatusForm
from .services import (
    create_task, update_task, change_status, reassign_task, 
    cancel_task, add_comment, add_or_replace_attachment,
    remove_attachment
)
from .permissions import (
    can_view_task, can_edit_task, can_change_status,
    can_cancel_task, can_reassign_task, get_viewable_tasks
)
from .filters import TaskFilter, DashboardTaskFilter, get_sorting_options, apply_sorting
from apps.departments.models import Department
from apps.accounts.models import User


# =============================================================================
# Dashboard Views
# =============================================================================

@login_required
def dashboard(request):
    """
    Main dashboard view with three tabs:
    - My Personal Tasks (tasks I created for myself)
    - Assigned to Me (tasks others delegated to me)
    - I Assigned (tasks I delegated to others)
    """
    user = request.user
    tab = request.GET.get('tab', 'personal')
    
    # Base querysets for each tab
    personal_tasks = Task.objects.filter(
        created_by=user,
        assignee=user,
        task_type='personal'
    ).exclude(status__in=['cancelled', 'verified', 'completed'])
    
    assigned_to_me = Task.objects.filter(
        assignee=user,
        task_type='delegated'
    ).exclude(status__in=['cancelled', 'verified'])
    
    i_assigned = Task.objects.filter(
        created_by=user,
        task_type='delegated'
    ).exclude(assignee=user).exclude(status__in=['cancelled', 'verified'])
    
    # Get counts for tabs
    personal_count = personal_tasks.count()
    assigned_count = assigned_to_me.count()
    i_assigned_count = i_assigned.count()
    
    # Get tasks for current tab
    if tab == 'personal':
        queryset = personal_tasks
    elif tab == 'assigned':
        queryset = assigned_to_me
    elif tab == 'delegated':
        queryset = i_assigned
    else:
        queryset = personal_tasks
        tab = 'personal'
    
    # Apply filters
    search = request.GET.get('search', '')
    status_filter = request.GET.getlist('status')
    priority_filter = request.GET.getlist('priority')
    
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(reference_number__icontains=search)
        )
    
    if status_filter:
        queryset = queryset.filter(status__in=status_filter)
    
    if priority_filter:
        queryset = queryset.filter(priority__in=priority_filter)
    
    # Order by deadline (nulls last), then by created_at
    queryset = queryset.select_related(
        'assignee', 'created_by', 'department'
    ).order_by(
        'status',  # pending first
        '-priority',  # high priority first
        'deadline',  # earliest deadline first
        '-created_at'
    )
    
    # Pagination
    paginator = Paginator(queryset, 20)
    page = request.GET.get('page', 1)
    
    try:
        tasks = paginator.page(page)
    except PageNotAnInteger:
        tasks = paginator.page(1)
    except EmptyPage:
        tasks = paginator.page(paginator.num_pages)
    
    context = {
        'tasks': tasks,
        'tab': tab,
        'personal_count': personal_count,
        'assigned_count': assigned_count,
        'i_assigned_count': i_assigned_count,
        'search': search,
        'selected_statuses': status_filter,
        'selected_priorities': priority_filter,
        'status_choices': Task.Status.choices,
        'priority_choices': Task.Priority.choices,
    }
    
    # Handle HTMX partial requests
    if request.htmx:
        return render(request, 'tasks/partials/dashboard_tasks.html', context)
    
    return render(request, 'tasks/dashboard.html', context)


# =============================================================================
# Task List View (Enhanced with Filters)
# =============================================================================

@login_required
def task_list(request):
    """
    Full task list view with comprehensive filtering and sorting.
    Accessible to all users, but content filtered by role.
    """
    user = request.user
    
    # Get base queryset based on user's role
    queryset = get_viewable_tasks(user)
    
    # Apply TaskFilter
    task_filter = TaskFilter(request.GET, queryset=queryset, request=request)
    filtered_queryset = task_filter.qs
    
    # Apply sorting
    sort_param = request.GET.get('sort', '-created_at')
    sorted_queryset = apply_sorting(filtered_queryset, sort_param)
    
    # Pagination (20 per page as per spec)
    paginator = Paginator(sorted_queryset, 20)
    page = request.GET.get('page', 1)
    
    try:
        tasks = paginator.page(page)
    except PageNotAnInteger:
        tasks = paginator.page(1)
    except EmptyPage:
        tasks = paginator.page(paginator.num_pages)
    
    # Determine which filters to show based on role
    show_department_filter = user.role in ['admin', 'senior_manager_1', 'senior_manager_2', 'manager']
    show_assignee_filter = user.role in ['admin', 'senior_manager_1', 'senior_manager_2', 'manager']
    
    # Get filter options
    if show_department_filter:
        if user.role in ['admin', 'senior_manager_1', 'senior_manager_2']:
            departments = Department.objects.all().order_by('name')
        else:
            departments = Department.objects.filter(pk=user.department_id) if user.department else Department.objects.none()
    else:
        departments = Department.objects.none()
    
    if show_assignee_filter:
        if user.role in ['admin', 'senior_manager_1', 'senior_manager_2']:
            assignees = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
        elif user.department:
            assignees = User.objects.filter(is_active=True, department=user.department).order_by('first_name', 'last_name')
        else:
            assignees = User.objects.none()
    else:
        assignees = User.objects.none()
    
    # Check for active filters
    has_active_filters = any([
        request.GET.get('search'),
        request.GET.getlist('status'),
        request.GET.getlist('priority'),
        request.GET.get('deadline_filter'),
        request.GET.get('department'),
        request.GET.get('assignee'),
        request.GET.get('task_type'),
    ])
    
    # Parse selected values for template
    try:
        selected_department = int(request.GET.get('department', '')) if request.GET.get('department') else None
    except ValueError:
        selected_department = None
    
    try:
        selected_assignee = int(request.GET.get('assignee', '')) if request.GET.get('assignee') else None
    except ValueError:
        selected_assignee = None
    
    context = {
        'tasks': tasks,
        'page_obj': tasks,
        'total_count': paginator.count,
        'filter': task_filter,
        'sorting_options': get_sorting_options(),
        'current_sort': sort_param,
        'has_active_filters': has_active_filters,
        'show_department_filter': show_department_filter,
        'show_assignee_filter': show_assignee_filter,
        'departments': departments,
        'assignees': assignees,
        'selected_statuses': request.GET.getlist('status'),
        'selected_priorities': request.GET.getlist('priority'),
        'selected_deadline_filter': request.GET.get('deadline_filter', ''),
        'selected_deadline_from': request.GET.get('deadline_from', ''),
        'selected_deadline_to': request.GET.get('deadline_to', ''),
        'selected_task_type': request.GET.get('task_type', ''),
        'selected_department': selected_department,
        'selected_assignee': selected_assignee,
    }
    
    # Handle HTMX requests - return only the task list content
    if request.htmx:
        return render(request, 'tasks/partials/task_list_content.html', context)
    
    return render(request, 'tasks/task_list.html', context)


# =============================================================================
# Task CRUD Views
# =============================================================================

@login_required
def task_create(request):
    """Create a new task."""
    if request.method == 'POST':
        form = TaskForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            try:
                task = create_task(
                    title=form.cleaned_data['title'],
                    description=form.cleaned_data.get('description', ''),
                    assignee=form.cleaned_data['assignee'],
                    created_by=request.user,
                    deadline=form.cleaned_data.get('deadline'),
                    priority=form.cleaned_data.get('priority', 'medium'),
                )
                
                # Handle attachment if provided
                if 'attachment' in request.FILES:
                    add_or_replace_attachment(
                        task=task,
                        user=request.user,
                        file=request.FILES['attachment']
                    )
                
                messages.success(request, f'Task {task.reference_number} created successfully.')
                return redirect('tasks:task_detail', pk=task.pk)
                
            except PermissionError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f'Error creating task: {str(e)}')
    else:
        form = TaskForm(user=request.user)
    
    return render(request, 'tasks/task_form.html', {
        'form': form,
        'title': 'Create Task',
        'submit_text': 'Create Task',
    })


@login_required
def task_detail(request, pk):
    """View task details with comments and attachment."""
    task = get_object_or_404(
        Task.objects.select_related(
            'assignee', 'created_by', 'department', 'cancelled_by'
        ).prefetch_related('comments__author', 'activities__user'),
        pk=pk
    )
    
    # Check view permission
    if not can_view_task(request.user, task):
        messages.error(request, 'You do not have permission to view this task.')
        return redirect('tasks:dashboard')
    
    # Get attachment if exists
    try:
        attachment = task.attachment
    except Attachment.DoesNotExist:
        attachment = None
    
    # Forms
    comment_form = CommentForm()
    attachment_form = AttachmentForm()
    status_form = TaskStatusForm(task=task, user=request.user)
    
    # Permissions for template
    can_edit = can_edit_task(request.user, task)
    can_status = can_change_status(request.user, task)
    can_cancel = can_cancel_task(request.user, task)
    can_reassign = can_reassign_task(request.user, task)
    
    context = {
        'task': task,
        'comments': task.comments.all().order_by('created_at'),
        'attachment': attachment,
        'activities': task.activities.all()[:20],
        'comment_form': comment_form,
        'attachment_form': attachment_form,
        'status_form': status_form,
        'can_edit': can_edit,
        'can_change_status': can_status,
        'can_cancel': can_cancel,
        'can_reassign': can_reassign,
    }
    
    return render(request, 'tasks/task_detail.html', context)


@login_required
def task_edit(request, pk):
    """Edit an existing task."""
    task = get_object_or_404(Task, pk=pk)
    
    # Check edit permission
    if not can_edit_task(request.user, task):
        messages.error(request, 'You do not have permission to edit this task.')
        return redirect('tasks:task_detail', pk=pk)
    
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task, user=request.user)
        if form.is_valid():
            try:
                updated_task = update_task(
                    task=task,
                    user=request.user,
                    title=form.cleaned_data['title'],
                    description=form.cleaned_data.get('description', ''),
                    priority=form.cleaned_data.get('priority'),
                    deadline=form.cleaned_data.get('deadline'),
                )
                messages.success(request, 'Task updated successfully.')
                return redirect('tasks:task_detail', pk=pk)
                
            except Exception as e:
                messages.error(request, f'Error updating task: {str(e)}')
    else:
        form = TaskForm(instance=task, user=request.user)
    
    return render(request, 'tasks/task_form.html', {
        'form': form,
        'task': task,
        'title': f'Edit Task: {task.reference_number}',
        'submit_text': 'Save Changes',
    })


# =============================================================================
# Status Change Views
# =============================================================================

@login_required
@require_http_methods(["GET", "POST"])
def task_status_change(request, pk):
    """Change task status with form."""
    task = get_object_or_404(Task, pk=pk)
    
    if not can_change_status(request.user, task):
        messages.error(request, 'You do not have permission to change this task\'s status.')
        return redirect('tasks:task_detail', pk=pk)
    
    if request.method == 'POST':
        form = TaskStatusForm(request.POST, task=task, user=request.user)
        if form.is_valid():
            try:
                new_status = form.cleaned_data['status']
                change_status(task, request.user, new_status)
                messages.success(request, f'Task status changed to {task.get_status_display()}.')
                return redirect('tasks:task_detail', pk=pk)
            except Exception as e:
                messages.error(request, str(e))
    else:
        form = TaskStatusForm(task=task, user=request.user)
    
    return render(request, 'tasks/task_status_change.html', {
        'task': task,
        'form': form,
    })


@login_required
@require_POST
def quick_status_change(request, pk):
    """
    HTMX endpoint for quick status changes from list view.
    Returns updated task list content.
    """
    task = get_object_or_404(Task, pk=pk)
    
    if not can_change_status(request.user, task):
        return HttpResponseForbidden('Permission denied')
    
    new_status = request.POST.get('status')
    if not new_status:
        return HttpResponse('Status required', status=400)
    
    try:
        change_status(task, request.user, new_status)
        messages.success(request, f'Task marked as {task.get_status_display()}.')
    except Exception as e:
        messages.error(request, str(e))
    
    # Return to task list with current filters
    return task_list(request)


# =============================================================================
# Task Reassign & Cancel Views
# =============================================================================

@login_required
@require_http_methods(["GET", "POST"])
def task_reassign(request, pk):
    """Reassign task to a different user."""
    task = get_object_or_404(Task, pk=pk)
    
    if not can_reassign_task(request.user, task):
        messages.error(request, 'You do not have permission to reassign this task.')
        return redirect('tasks:task_detail', pk=pk)
    
    if request.method == 'POST':
        new_assignee_id = request.POST.get('assignee')
        if new_assignee_id:
            try:
                new_assignee = User.objects.get(pk=new_assignee_id, is_active=True)
                reassign_task(task, request.user, new_assignee)
                messages.success(request, f'Task reassigned to {new_assignee.get_full_name()}.')
                return redirect('tasks:task_detail', pk=pk)
            except User.DoesNotExist:
                messages.error(request, 'Selected user not found.')
            except Exception as e:
                messages.error(request, str(e))
    
    # Get possible assignees based on user's role
    user = request.user
    if user.role in ['admin', 'senior_manager_1', 'senior_manager_2']:
        assignees = User.objects.filter(is_active=True).exclude(pk=task.assignee_id)
    elif user.role == 'manager' and user.department:
        assignees = User.objects.filter(
            is_active=True,
            department=user.department
        ).exclude(pk=task.assignee_id)
    else:
        assignees = User.objects.none()
    
    return render(request, 'tasks/task_reassign.html', {
        'task': task,
        'assignees': assignees.order_by('first_name', 'last_name'),
    })


@login_required
@require_http_methods(["GET", "POST"])
def task_cancel(request, pk):
    """Cancel a task with optional reason."""
    task = get_object_or_404(Task, pk=pk)
    
    if not can_cancel_task(request.user, task):
        messages.error(request, 'You do not have permission to cancel this task.')
        return redirect('tasks:task_detail', pk=pk)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        try:
            cancel_task(task, request.user, reason)
            messages.success(request, 'Task cancelled successfully.')
            return redirect('tasks:task_detail', pk=pk)
        except Exception as e:
            messages.error(request, str(e))
    
    return render(request, 'tasks/task_cancel.html', {'task': task})


# =============================================================================
# Comment Views
# =============================================================================

@login_required
@require_POST
def add_comment_view(request, pk):
    """Add a comment to a task (HTMX endpoint)."""
    task = get_object_or_404(Task, pk=pk)
    
    if not can_view_task(request.user, task):
        return HttpResponseForbidden('Permission denied')
    
    form = CommentForm(request.POST)
    if form.is_valid():
        try:
            comment = add_comment(
                task=task,
                user=request.user,
                content=form.cleaned_data['content']
            )
            
            if request.htmx:
                # Return just the new comment for HTMX append
                return render(request, 'tasks/partials/comment.html', {
                    'comment': comment,
                    'task': task,
                })
            
            messages.success(request, 'Comment added.')
            return redirect('tasks:task_detail', pk=pk)
            
        except Exception as e:
            if request.htmx:
                return HttpResponse(f'Error: {str(e)}', status=400)
            messages.error(request, str(e))
    
    if request.htmx:
        return HttpResponse('Invalid comment', status=400)
    
    return redirect('tasks:task_detail', pk=pk)


# =============================================================================
# Attachment Views
# =============================================================================

@login_required
@require_POST
def upload_attachment(request, pk):
    """Upload or replace task attachment."""
    task = get_object_or_404(Task, pk=pk)
    
    if not can_view_task(request.user, task):
        messages.error(request, 'Permission denied')
        return redirect('tasks:task_detail', pk=pk)
    
    form = AttachmentForm(request.POST, request.FILES)
    if form.is_valid() and 'file' in request.FILES:
        try:
            add_or_replace_attachment(
                task=task,
                user=request.user,
                file=request.FILES['file']
            )
            messages.success(request, 'Attachment uploaded successfully.')
        except Exception as e:
            messages.error(request, str(e))
    else:
        messages.error(request, 'Please select a valid file.')
    
    return redirect('tasks:task_detail', pk=pk)


@login_required
def download_attachment(request, pk):
    """Download task attachment."""
    task = get_object_or_404(Task, pk=pk)
    
    if not can_view_task(request.user, task):
        return HttpResponseForbidden('Permission denied')
    
    try:
        attachment = task.attachment
        return FileResponse(
            attachment.file.open('rb'),
            as_attachment=True,
            filename=attachment.filename
        )
    except Attachment.DoesNotExist:
        messages.error(request, 'No attachment found.')
        return redirect('tasks:task_detail', pk=pk)


@login_required
@require_POST
def remove_attachment_view(request, pk):
    """Remove task attachment (HTMX endpoint)."""
    task = get_object_or_404(Task, pk=pk)
    
    if not can_edit_task(request.user, task):
        return HttpResponseForbidden('Permission denied')
    
    try:
        remove_attachment(task, request.user)
        
        if request.htmx:
            # Return empty attachment section
            return render(request, 'tasks/partials/attachment_section.html', {
                'task': task,
                'attachment': None,
                'attachment_form': AttachmentForm(),
                'can_edit': True,
            })
        
        messages.success(request, 'Attachment removed.')
    except Exception as e:
        if request.htmx:
            return HttpResponse(str(e), status=400)
        messages.error(request, str(e))
    
    return redirect('tasks:task_detail', pk=pk)


# =============================================================================
# HTMX Partial Views
# =============================================================================

@login_required
def partials_task_row(request, pk):
    """Return a single task row for HTMX updates."""
    task = get_object_or_404(
        Task.objects.select_related('assignee', 'created_by', 'department'),
        pk=pk
    )
    
    if not can_view_task(request.user, task):
        return HttpResponseForbidden('Permission denied')
    
    return render(request, 'tasks/partials/task_row.html', {'task': task})


@login_required
def partials_badge_counts(request):
    """Return badge counts for navigation."""
    user = request.user
    
    # Count pending tasks assigned to user
    pending_count = Task.objects.filter(
        assignee=user,
        status__in=['pending', 'in_progress']
    ).count()
    
    # Count overdue tasks
    overdue_count = Task.objects.filter(
        assignee=user,
        status__in=['pending', 'in_progress'],
        deadline__lt=timezone.now()
    ).count()
    
    return render(request, 'tasks/partials/badge_counts.html', {
        'pending_count': pending_count,
        'overdue_count': overdue_count,
    })
