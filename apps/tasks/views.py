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
from django.db.models import Q, Count, Case, When, IntegerField
from django.utils import timezone

from .models import Task, Comment, Attachment
from .forms import TaskForm, CommentForm, AttachmentForm, TaskStatusForm
from .services import (
    create_task, update_task, change_status, reassign_task, 
    cancel_task, add_comment, add_or_replace_attachment,
    remove_attachment
)
from .permissions import (
    can_view_task, can_edit_task, can_change_status, can_change_task_status,
    can_cancel_task, can_reassign_task, get_viewable_tasks, get_allowed_status_transitions, get_visible_tasks
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


@login_required
def kanban(request):
    """
    Kanban board view with drag-and-drop status changes.
    """
    from .models import Task
    from .filters import TaskFilter
    
    user = request.user
    
    # Get base queryset based on role
    base_queryset = get_visible_tasks(user)
    
    # Exclude cancelled tasks from Kanban
    base_queryset = base_queryset.exclude(status=Task.Status.CANCELLED)
    
    # Apply filters (except status)
    filter_params = request.GET.copy()
    filter_params.pop('status', None)
    
    task_filter = TaskFilter(filter_params, queryset=base_queryset, request=request)
    filtered_queryset = task_filter.qs
    
    # Group tasks by status (max 50 per column)
    pending_tasks = filtered_queryset.filter(
        status=Task.Status.PENDING
    ).select_related('assignee', 'created_by', 'department')[:50]
    
    in_progress_tasks = filtered_queryset.filter(
        status=Task.Status.IN_PROGRESS
    ).select_related('assignee', 'created_by', 'department')[:50]
    
    completed_tasks = filtered_queryset.filter(
        status=Task.Status.COMPLETED
    ).select_related('assignee', 'created_by', 'department')[:50]
    
    verified_tasks = filtered_queryset.filter(
        status=Task.Status.VERIFIED
    ).select_related('assignee', 'created_by', 'department')[:50]
    
    # Count totals
    pending_count = filtered_queryset.filter(status=Task.Status.PENDING).count()
    in_progress_count = filtered_queryset.filter(status=Task.Status.IN_PROGRESS).count()
    completed_count = filtered_queryset.filter(status=Task.Status.COMPLETED).count()
    verified_count = filtered_queryset.filter(status=Task.Status.VERIFIED).count()
    
    columns = [
        {
            'id': 'pending',
            'status': Task.Status.PENDING,
            'title': 'Pending',
            'tasks': pending_tasks,
            'count': pending_count,
            'color': 'yellow',
        },
        {
            'id': 'in_progress',
            'status': Task.Status.IN_PROGRESS,
            'title': 'In Progress',
            'tasks': in_progress_tasks,
            'count': in_progress_count,
            'color': 'blue',
        },
        {
            'id': 'completed',
            'status': Task.Status.COMPLETED,
            'title': 'Completed',
            'tasks': completed_tasks,
            'count': completed_count,
            'color': 'green',
        },
        {
            'id': 'verified',
            'status': Task.Status.VERIFIED,
            'title': 'Verified',
            'tasks': verified_tasks,
            'count': verified_count,
            'color': 'emerald',
        },
    ]
    
    context = {
        'columns': columns,
        'filter': task_filter,
        'view_mode': 'kanban',
        'total_tasks': pending_count + in_progress_count + completed_count + verified_count,
    }
    
    return render(request, 'tasks/kanban.html', context)


@login_required
@require_POST
def kanban_move(request, pk):
    """
    HTMX endpoint to update task status via drag-and-drop.
    """
    from .models import Task
    
    user = request.user
    new_status = request.POST.get('new_status')
    
    # Validate new_status
    valid_statuses = [choice[0] for choice in Task.Status.choices]
    if not new_status or new_status not in valid_statuses:
        return HttpResponse(
            '<div class="text-red-600 text-sm p-2">Invalid status</div>',
            status=400
        )
    
    # Get the task
    try:
        task = Task.objects.select_related(
            'assignee', 'created_by', 'department'
        ).get(pk=pk)
    except Task.DoesNotExist:
        return HttpResponse(
            '<div class="text-red-600 text-sm p-2">Task not found</div>',
            status=404
        )
    
    # Check permissions
    if not can_change_task_status(user, task):
        return HttpResponse(
            '<div class="text-red-600 text-sm p-2">Permission denied</div>',
            status=403
        )
    
    # Check if transition is valid
    allowed_transitions = get_allowed_status_transitions(task, user)
    if new_status not in allowed_transitions:
        error_msg = f"Cannot move from {task.get_status_display()} to {dict(Task.Status.choices).get(new_status)}"
        return HttpResponse(
            f'<div class="text-red-600 text-sm p-2">{error_msg}</div>',
            status=400
        )
    
    # Check for personal completed tasks
    if task.is_personal and task.status == Task.Status.COMPLETED:
        return HttpResponse(
            '<div class="text-red-600 text-sm p-2">Personal completed tasks cannot be moved</div>',
            status=400
        )
    
    # Perform the status change
    try:
        task = change_status(task, user, new_status)
    except PermissionError as e:
        return HttpResponse(
            f'<div class="text-red-600 text-sm p-2">{str(e)}</div>',
            status=403
        )
    except ValueError as e:
        return HttpResponse(
            f'<div class="text-red-600 text-sm p-2">{str(e)}</div>',
            status=400
        )
    
    # Return updated task card
    return render(request, 'tasks/partials/task_card.html', {'task': task, 'user': user})


@login_required
def kanban_column(request, status):
    """
    HTMX endpoint to refresh a single Kanban column.
    """
    from .models import Task
    from .filters import TaskFilter
    
    user = request.user
    
    valid_statuses = {
        'pending': Task.Status.PENDING,
        'in_progress': Task.Status.IN_PROGRESS,
        'completed': Task.Status.COMPLETED,
        'verified': Task.Status.VERIFIED,
    }
    
    if status not in valid_statuses:
        return HttpResponse('Invalid status', status=400)
    
    task_status = valid_statuses[status]
    
    base_queryset = get_visible_tasks(user)
    filter_params = request.GET.copy()
    filter_params.pop('status', None)
    
    task_filter = TaskFilter(filter_params, queryset=base_queryset, request=request)
    filtered_queryset = task_filter.qs
    
    tasks = filtered_queryset.filter(
        status=task_status
    ).select_related('assignee', 'created_by', 'department')[:50]
    
    count = filtered_queryset.filter(status=task_status).count()
    
    colors = {
        'pending': 'yellow',
        'in_progress': 'blue',
        'completed': 'green',
        'verified': 'emerald',
    }
    
    column = {
        'id': status,
        'status': task_status,
        'title': dict(Task.Status.choices).get(task_status),
        'tasks': tasks,
        'count': count,
        'color': colors.get(status, 'gray'),
    }
    
    return render(request, 'tasks/partials/kanban_column.html', {'column': column})

"""
Phase 6D: Department Tasks & Management Overview Views
Add these functions to apps/tasks/views.py

INSTRUCTIONS:
1. Add the imports at the top of your views.py (merge with existing imports)
2. Add both view functions at the end of your views.py file
"""


# ============================================================================
# NEW VIEW FUNCTIONS - Add these to apps/tasks/views.py
# ============================================================================


@login_required
def department_tasks(request):
    """
    Department-scoped task list view.
    
    Permissions:
    - Employee: Redirected to dashboard (no access)
    - Manager: Sees only their department's tasks
    - Senior Manager/Admin: Sees all tasks with department filter
    """
    user = request.user
    
    # Employee cannot access this view
    if user.is_employee():
        messages.warning(request, "You don't have permission to view department tasks.")
        return redirect('tasks:dashboard')
    
    # Base queryset with optimizations
    queryset = Task.objects.select_related(
        'assignee', 'created_by', 'department'
    ).prefetch_related('comments')
    
    # Determine scope based on role
    if user.is_manager():
        # Manager sees only their department
        if not user.department:
            messages.error(request, "You are not assigned to any department.")
            return redirect('tasks:dashboard')
        
        queryset = queryset.filter(department=user.department)
        departments = None  # No department filter for managers
        current_department = user.department
        can_filter_department = False
    else:
        # Senior Manager/Admin sees all with optional department filter
        from apps.departments.models import Department
        departments = Department.objects.all().order_by('name')
        can_filter_department = True
        
        # Apply department filter if selected
        department_id = request.GET.get('department')
        if department_id:
            try:
                current_department = Department.objects.get(pk=department_id)
                queryset = queryset.filter(department=current_department)
            except Department.DoesNotExist:
                current_department = None
        else:
            current_department = None
    
    # Apply filters using TaskFilter
    from .filters import TaskFilter
    task_filter = TaskFilter(request.GET, queryset=queryset, request=request)
    filtered_queryset = task_filter.qs
    
    # Apply sorting
    sort = request.GET.get('sort', '-created_at')
    valid_sorts = [
        'deadline', '-deadline', 'created_at', '-created_at',
        'priority', '-priority', 'status', '-status', 'title', '-title'
    ]
    if sort in valid_sorts:
        # Handle priority sorting (custom order)
        if sort == 'priority':
            filtered_queryset = filtered_queryset.annotate(
                priority_order=Case(
                    When(priority='critical', then=0),
                    When(priority='high', then=1),
                    When(priority='medium', then=2),
                    When(priority='low', then=3),
                    output_field=IntegerField(),
                )
            ).order_by('priority_order')
        elif sort == '-priority':
            filtered_queryset = filtered_queryset.annotate(
                priority_order=Case(
                    When(priority='critical', then=0),
                    When(priority='high', then=1),
                    When(priority='medium', then=2),
                    When(priority='low', then=3),
                    output_field=IntegerField(),
                )
            ).order_by('-priority_order')
        else:
            filtered_queryset = filtered_queryset.order_by(sort)
    else:
        filtered_queryset = filtered_queryset.order_by('-created_at')
    
    # Pagination
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(filtered_queryset, 20)
    page = request.GET.get('page', 1)
    
    try:
        tasks = paginator.page(page)
    except PageNotAnInteger:
        tasks = paginator.page(1)
    except EmptyPage:
        tasks = paginator.page(paginator.num_pages)
    
    # Calculate summary stats for current view
    stats = {
        'total': filtered_queryset.count(),
        'pending': filtered_queryset.filter(status='pending').count(),
        'in_progress': filtered_queryset.filter(status='in_progress').count(),
        'completed': filtered_queryset.filter(status='completed').count(),
        'overdue': filtered_queryset.filter(
            deadline__lt=timezone.now(),
            status__in=['pending', 'in_progress']
        ).count(),
    }
    
    # Get department head info if viewing a specific department
    department_head = None
    if current_department and current_department.head:
        department_head = current_department.head
    
    context = {
        'tasks': tasks,
        'filter': task_filter,
        'current_sort': sort,
        'departments': departments,
        'current_department': current_department,
        'can_filter_department': can_filter_department,
        'department_head': department_head,
        'stats': stats,
        'page_title': f'{current_department.name} Tasks' if current_department else 'All Department Tasks',
    }
    
    # Handle HTMX requests
    if request.htmx:
        return render(request, 'tasks/partials/department_tasks_content.html', context)
    
    return render(request, 'tasks/department_tasks.html', context)


@login_required
def management_overview(request):
    """
    Management overview with aggregated statistics.
    
    Permissions:
    - Employee/Manager: Returns 403 Forbidden
    - Senior Manager/Admin: Full access
    
    Shows:
    - Summary cards (Pending, In Progress, Completed, Overdue)
    - Breakdown by department
    - Breakdown by user
    """
    user = request.user
    
    # Only Senior Managers and Admin can access
    if not (user.is_senior_manager() or user.is_admin()):
        return HttpResponseForbidden(
            render(request, 'tasks/403_forbidden.html', {
                'message': 'Management overview is only accessible to Senior Managers and Administrators.'
            }).content
        )
    
    from apps.departments.models import Department
    from apps.accounts.models import User
    
    # Get all active tasks (not cancelled or verified)
    all_tasks = Task.objects.filter(
        status__in=['pending', 'in_progress', 'completed']
    ).select_related('assignee', 'department')
    
    now = timezone.now()
    
    # =========================================================================
    # SUMMARY STATISTICS
    # =========================================================================
    summary_stats = {
        'total_active': all_tasks.count(),
        'pending': all_tasks.filter(status='pending').count(),
        'in_progress': all_tasks.filter(status='in_progress').count(),
        'completed': all_tasks.filter(status='completed').count(),
        'overdue': all_tasks.filter(
            deadline__lt=now,
            status__in=['pending', 'in_progress']
        ).count(),
        'escalated_72h': all_tasks.filter(
            escalated_to_sm2_at__isnull=False,
            status__in=['pending', 'in_progress']
        ).count(),
        'escalated_120h': all_tasks.filter(
            escalated_to_sm1_at__isnull=False,
            status__in=['pending', 'in_progress']
        ).count(),
    }
    
    # =========================================================================
    # DEPARTMENT BREAKDOWN
    # =========================================================================
    departments = Department.objects.annotate(
        total_tasks=Count(
            'tasks',
            filter=Q(tasks__status__in=['pending', 'in_progress', 'completed'])
        ),
        pending_count=Count(
            'tasks',
            filter=Q(tasks__status='pending')
        ),
        in_progress_count=Count(
            'tasks',
            filter=Q(tasks__status='in_progress')
        ),
        completed_count=Count(
            'tasks',
            filter=Q(tasks__status='completed')
        ),
        overdue_count=Count(
            'tasks',
            filter=Q(
                tasks__deadline__lt=now,
                tasks__status__in=['pending', 'in_progress']
            )
        ),
    ).order_by('name')
    
    # =========================================================================
    # USER BREAKDOWN (Active users with tasks)
    # =========================================================================
    users_with_tasks = User.objects.filter(
        is_active=True
    ).annotate(
        total_assigned=Count(
            'assigned_tasks',
            filter=Q(assigned_tasks__status__in=['pending', 'in_progress', 'completed'])
        ),
        pending_count=Count(
            'assigned_tasks',
            filter=Q(assigned_tasks__status='pending')
        ),
        in_progress_count=Count(
            'assigned_tasks',
            filter=Q(assigned_tasks__status='in_progress')
        ),
        completed_count=Count(
            'assigned_tasks',
            filter=Q(assigned_tasks__status='completed')
        ),
        overdue_count=Count(
            'assigned_tasks',
            filter=Q(
                assigned_tasks__deadline__lt=now,
                assigned_tasks__status__in=['pending', 'in_progress']
            )
        ),
    ).filter(
        total_assigned__gt=0  # Only users with tasks
    ).select_related('department').order_by('department__name', 'first_name', 'last_name')
    
    # Pagination for user breakdown
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(users_with_tasks, 25)
    page = request.GET.get('page', 1)
    
    try:
        users_page = paginator.page(page)
    except PageNotAnInteger:
        users_page = paginator.page(1)
    except EmptyPage:
        users_page = paginator.page(paginator.num_pages)
    
    # =========================================================================
    # OVERDUE TASKS LIST (Top 10)
    # =========================================================================
    overdue_tasks = Task.objects.filter(
        deadline__lt=now,
        status__in=['pending', 'in_progress']
    ).select_related(
        'assignee', 'created_by', 'department'
    ).order_by('deadline')[:10]
    
    # =========================================================================
    # ESCALATED TASKS LIST (Top 10)
    # =========================================================================
    escalated_tasks = Task.objects.filter(
        Q(escalated_to_sm2_at__isnull=False) | Q(escalated_to_sm1_at__isnull=False),
        status__in=['pending', 'in_progress']
    ).select_related(
        'assignee', 'created_by', 'department'
    ).order_by('deadline')[:10]
    
    context = {
        'summary_stats': summary_stats,
        'departments': departments,
        'users_page': users_page,
        'overdue_tasks': overdue_tasks,
        'escalated_tasks': escalated_tasks,
        'page_title': 'Management Overview',
    }
    
    return render(request, 'tasks/management_overview.html', context)