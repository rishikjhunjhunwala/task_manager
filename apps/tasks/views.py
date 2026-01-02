"""
Views for tasks app.

Includes:
- Dashboard with tabs (My Personal, Assigned to Me, I Assigned)
- Task CRUD operations
- Task list with filtering and sorting
- Status changes (form and HTMX quick change)
- Comments and attachments (HTMX-enabled)

Updated in Phase 7B:
- upload_attachment: Uses can_add_attachment, returns HTMX partial
- remove_attachment_view: Uses can_remove_attachment, returns HTMX partial
- task_detail: Added can_attachment and can_remove to context
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden, FileResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count, Case, When, IntegerField
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import Task, Comment, Attachment
from .forms import TaskForm, CommentForm, AttachmentForm, TaskStatusForm
from .services import (
    create_task, update_task, change_status, reassign_task, 
    cancel_task, add_comment, add_or_replace_attachment,
    remove_attachment
)
from .permissions import (
    can_view_task, can_edit_task, can_change_status, can_change_task_status,
    can_cancel_task, can_reassign_task, get_viewable_tasks, 
    get_allowed_status_transitions, get_visible_tasks, 
    can_add_comment, can_add_attachment, can_remove_attachment  # Added in Phase 7B
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
    - My Personal: Tasks where user is both creator and assignee
    - Assigned to Me: Tasks assigned to user by others
    - I Assigned: Tasks user created and assigned to others
    """
    user = request.user
    
    # Get base queryset optimized with select_related
    base_queryset = Task.objects.select_related(
        'assignee', 'created_by', 'department'
    ).exclude(status='cancelled')
    
    # Tab-specific filters
    my_personal = base_queryset.filter(
        created_by=user,
        assignee=user,
        task_type='personal'
    )
    
    assigned_to_me = base_queryset.filter(
        assignee=user,
        task_type='delegated'
    )
    
    i_assigned = base_queryset.filter(
        created_by=user,
        task_type='delegated'
    ).exclude(assignee=user)
    
    # Apply dashboard filters if provided
    filter_form = DashboardTaskFilter(request.GET)
    
    if filter_form.is_valid():
        status = filter_form.cleaned_data.get('status')
        priority = filter_form.cleaned_data.get('priority')
        deadline_filter = filter_form.cleaned_data.get('deadline_filter')
        
        for qs_name in ['my_personal', 'assigned_to_me', 'i_assigned']:
            qs = locals()[qs_name]
            
            if status:
                qs = qs.filter(status=status)
            if priority:
                qs = qs.filter(priority=priority)
            if deadline_filter:
                qs = filter_form.apply_deadline_filter(qs, deadline_filter)
            
            locals()[qs_name] = qs
    
    # Get active tab
    active_tab = request.GET.get('tab', 'my_personal')
    if active_tab not in ['my_personal', 'assigned_to_me', 'i_assigned']:
        active_tab = 'my_personal'
    
    # Sort by priority and deadline
    order_by = ['-priority', 'deadline', '-created_at']
    my_personal = my_personal.order_by(*order_by)[:20]
    assigned_to_me = assigned_to_me.order_by(*order_by)[:20]
    i_assigned = i_assigned.order_by(*order_by)[:20]
    
    # Count badges
    badge_counts = {
        'my_personal': my_personal.count(),
        'assigned_to_me': assigned_to_me.count(),
        'i_assigned': i_assigned.count(),
    }
    
    context = {
        'my_personal': my_personal,
        'assigned_to_me': assigned_to_me,
        'i_assigned': i_assigned,
        'active_tab': active_tab,
        'filter_form': filter_form,
        'badge_counts': badge_counts,
    }
    
    return render(request, 'tasks/dashboard.html', context)


# =============================================================================
# Task List View
# =============================================================================

@login_required
def task_list(request):
    """Full task list with advanced filtering and sorting."""
    user = request.user
    
    # Get viewable tasks based on role
    queryset = get_viewable_tasks(user)
    
    # Apply filters
    filter_form = TaskFilter(request.GET, user=user)
    if filter_form.is_valid():
        queryset = filter_form.filter_queryset(queryset)
    
    # Apply sorting
    sort_options = get_sorting_options()
    sort_by = request.GET.get('sort', '-created_at')
    queryset = apply_sorting(queryset, sort_by)
    
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
        'filter_form': filter_form,
        'sort_options': sort_options,
        'current_sort': sort_by,
        'total_count': paginator.count,
    }
    
    return render(request, 'tasks/task_list.html', context)


# =============================================================================
# Task CRUD Views
# =============================================================================

@login_required
def task_create(request):
    """Create a new task."""
    if request.method == 'POST':
        form = TaskForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                task = create_task(
                    title=form.cleaned_data['title'],
                    description=form.cleaned_data.get('description', ''),
                    creator=request.user,
                    assignee=form.cleaned_data['assignee'],
                    deadline=form.cleaned_data.get('deadline'),
                    priority=form.cleaned_data.get('priority', 'medium'),
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
    can_comment = can_add_comment(request.user, task)
    
    # Phase 7B: Add attachment permissions to context
    can_attachment = can_add_attachment(request.user, task)
    can_remove = can_remove_attachment(request.user, task)
    
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
        'can_comment': can_comment,
        # Phase 7B additions
        'can_attachment': can_attachment,
        'can_remove': can_remove,
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
        form = TaskForm(request.POST, user=request.user, instance=task)
        if form.is_valid():
            try:
                update_task(
                    task=task,
                    user=request.user,
                    title=form.cleaned_data['title'],
                    description=form.cleaned_data.get('description', ''),
                    deadline=form.cleaned_data.get('deadline'),
                    priority=form.cleaned_data.get('priority', 'medium'),
                )
                messages.success(request, 'Task updated successfully.')
                return redirect('tasks:task_detail', pk=pk)
                
            except PermissionError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f'Error updating task: {str(e)}')
    else:
        form = TaskForm(user=request.user, instance=task)
    
    return render(request, 'tasks/task_form.html', {
        'form': form,
        'task': task,
        'title': f'Edit Task {task.reference_number}',
        'submit_text': 'Save Changes',
    })


# =============================================================================
# Status Change Views
# =============================================================================

@login_required
@require_POST
def task_status_change(request, pk):
    """Change task status via form submission."""
    task = get_object_or_404(Task, pk=pk)
    
    if not can_change_status(request.user, task):
        messages.error(request, 'You do not have permission to change this task status.')
        return redirect('tasks:task_detail', pk=pk)
    
    form = TaskStatusForm(request.POST, task=task, user=request.user)
    if form.is_valid():
        new_status = form.cleaned_data['new_status']
        try:
            change_status(task, request.user, new_status)
            messages.success(request, f'Task status changed to {task.get_status_display()}.')
        except Exception as e:
            messages.error(request, str(e))
    else:
        messages.error(request, 'Invalid status transition.')
    
    return redirect('tasks:task_detail', pk=pk)


@login_required
@require_POST
def quick_status_change(request, pk):
    """HTMX endpoint for quick status change."""
    task = get_object_or_404(Task, pk=pk)
    
    if not can_change_status(request.user, task):
        return HttpResponseForbidden('Permission denied')
    
    new_status = request.POST.get('status')
    if not new_status:
        return HttpResponse('Missing status', status=400)
    
    try:
        change_status(task, request.user, new_status)
        
        # Return updated task row partial for HTMX
        if request.headers.get('HX-Request'):
            return render(request, 'tasks/partials/task_row.html', {'task': task})
        
        return redirect('tasks:task_detail', pk=pk)
        
    except Exception as e:
        if request.headers.get('HX-Request'):
            return HttpResponse(str(e), status=400)
        messages.error(request, str(e))
        return redirect('tasks:task_detail', pk=pk)


# =============================================================================
# Task Actions (Reassign, Cancel)
# =============================================================================

@login_required
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
                new_assignee = User.objects.get(pk=new_assignee_id)
                reassign_task(task, request.user, new_assignee)
                messages.success(request, f'Task reassigned to {new_assignee.get_full_name()}.')
                return redirect('tasks:task_detail', pk=pk)
            except User.DoesNotExist:
                messages.error(request, 'Selected user not found.')
            except Exception as e:
                messages.error(request, str(e))
    
    # Get assignable users for the form
    from .permissions import get_assignable_users
    assignable_users = get_assignable_users(request.user)
    
    return render(request, 'tasks/task_reassign.html', {
        'task': task,
        'assignable_users': assignable_users,
    })


@login_required
def task_cancel(request, pk):
    """Cancel a task."""
    task = get_object_or_404(Task, pk=pk)
    
    if not can_cancel_task(request.user, task):
        messages.error(request, 'You do not have permission to cancel this task.')
        return redirect('tasks:task_detail', pk=pk)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, 'Please provide a reason for cancellation.')
        else:
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
    
    # Check permission using updated function
    if not can_add_comment(request.user, task):
        error_msg = 'You do not have permission to comment on this task.'
        if task.status == 'cancelled':
            error_msg = 'Cannot add comments to cancelled tasks.'
        
        if request.headers.get('HX-Request'):
            return HttpResponse(
                f'<div class="text-red-600 text-sm p-2">{error_msg}</div>',
                status=403
            )
        messages.error(request, error_msg)
        return redirect('tasks:task_detail', pk=pk)
    
    form = CommentForm(request.POST)
    
    if form.is_valid():
        try:
            # Use the service layer to add comment (handles validation & activity logging)
            comment = add_comment(
                task=task,
                user=request.user,
                content=form.cleaned_data['content']
            )
            
            # HTMX Response: Return just the new comment partial
            if request.headers.get('HX-Request'):
                return render(request, 'tasks/partials/comment.html', {
                    'comment': comment,
                })
            
            # Non-HTMX Fallback
            messages.success(request, 'Comment added successfully.')
            return redirect('tasks:task_detail', pk=pk)
            
        except PermissionError as e:
            error_msg = str(e)
            if request.headers.get('HX-Request'):
                return HttpResponse(
                    f'<div class="text-red-600 text-sm p-2">{error_msg}</div>',
                    status=403
                )
            messages.error(request, error_msg)
            return redirect('tasks:task_detail', pk=pk)
            
        except Exception as e:
            error_msg = f'Error adding comment: {str(e)}'
            if request.headers.get('HX-Request'):
                return HttpResponse(
                    f'<div class="text-red-600 text-sm p-2">{error_msg}</div>',
                    status=400
                )
            messages.error(request, error_msg)
            return redirect('tasks:task_detail', pk=pk)
    
    # Form validation failed
    error_msg = 'Comment cannot be empty.'
    if form.errors:
        error_msg = '; '.join([f'{field}: {", ".join(errors)}' for field, errors in form.errors.items()])
    
    if request.headers.get('HX-Request'):
        return HttpResponse(
            f'<div class="text-red-600 text-sm p-2">{error_msg}</div>',
            status=400
        )
    
    messages.error(request, error_msg)
    return redirect('tasks:task_detail', pk=pk)


# =============================================================================
# Attachment Views (UPDATED in Phase 7B)
# =============================================================================

@login_required
@require_POST
def upload_attachment(request, pk):
    """
    Upload or replace task attachment (HTMX-enabled).
    
    Phase 7B Updates:
    - Uses can_add_attachment for permission check (not can_view_task)
    - Returns attachment_section.html partial for HTMX requests
    - Proper error handling with validation messages
    """
    task = get_object_or_404(Task, pk=pk)
    
    # Phase 7B: Use correct permission check
    if not can_add_attachment(request.user, task):
        error_msg = 'You do not have permission to add attachments to this task.'
        
        if task.status == 'cancelled':
            error_msg = 'Cannot add attachments to cancelled tasks.'
        elif task.status == 'verified':
            error_msg = 'Cannot add attachments to verified tasks.'
        
        if request.headers.get('HX-Request'):
            return HttpResponse(
                f'<div class="text-red-600 text-sm p-2 bg-red-50 rounded">{error_msg}</div>',
                status=403
            )
        messages.error(request, error_msg)
        return redirect('tasks:task_detail', pk=pk)
    
    # Check if file was provided
    if 'file' not in request.FILES:
        if request.headers.get('HX-Request'):
            return HttpResponse(
                '<div class="text-red-600 text-sm p-2 bg-red-50 rounded">Please select a file to upload.</div>',
                status=400
            )
        messages.error(request, 'Please select a file to upload.')
        return redirect('tasks:task_detail', pk=pk)
    
    try:
        # Use service layer to handle upload (validates type + size)
        add_or_replace_attachment(
            task=task,
            user=request.user,
            file=request.FILES['file']
        )
        
        # HTMX Response: Return updated attachment section
        if request.headers.get('HX-Request'):
            # Refresh task to get updated attachment
            task.refresh_from_db()
            try:
                attachment = task.attachment
            except Attachment.DoesNotExist:
                attachment = None
            
            return render(request, 'tasks/partials/attachment_section.html', {
                'task': task,
                'attachment': attachment,
                'attachment_form': AttachmentForm(),
                'can_attachment': can_add_attachment(request.user, task),
                'can_remove': can_remove_attachment(request.user, task),
            })
        
        messages.success(request, 'Attachment uploaded successfully.')
        
    except ValidationError as e:
        error_msg = str(e)
        if request.headers.get('HX-Request'):
            return HttpResponse(
                f'<div class="text-red-600 text-sm p-2 bg-red-50 rounded">{error_msg}</div>',
                status=400
            )
        messages.error(request, error_msg)
        
    except PermissionError as e:
        error_msg = str(e)
        if request.headers.get('HX-Request'):
            return HttpResponse(
                f'<div class="text-red-600 text-sm p-2 bg-red-50 rounded">{error_msg}</div>',
                status=403
            )
        messages.error(request, error_msg)
        
    except Exception as e:
        error_msg = f'Upload failed: {str(e)}'
        if request.headers.get('HX-Request'):
            return HttpResponse(
                f'<div class="text-red-600 text-sm p-2 bg-red-50 rounded">{error_msg}</div>',
                status=500
            )
        messages.error(request, error_msg)
    
    return redirect('tasks:task_detail', pk=pk)


@login_required
def download_attachment(request, pk):
    """
    Download task attachment.
    
    Security:
    - Only users who can view the task can download
    - Files served through view, not direct media URL
    - Original filename preserved in Content-Disposition header
    
    Returns:
    - FileResponse with proper headers for browser download
    - Redirect to task detail if no attachment exists
    """
    import mimetypes
    
    task = get_object_or_404(Task, pk=pk)
    
    # Permission check - anyone who can view the task can download
    if not can_view_task(request.user, task):
        return HttpResponseForbidden('Permission denied')
    
    try:
        attachment = task.attachment
        
        # Detect MIME type from filename
        content_type, _ = mimetypes.guess_type(attachment.filename)
        if content_type is None:
            content_type = 'application/octet-stream'
        
        # Create streaming response
        response = FileResponse(
            attachment.file.open('rb'),
            as_attachment=True,
            filename=attachment.filename,
            content_type=content_type
        )
        
        # Set content length for download progress
        response['Content-Length'] = attachment.file_size
        
        return response
        
    except Attachment.DoesNotExist:
        messages.error(request, 'No attachment found.')
        return redirect('tasks:task_detail', pk=pk)
    except FileNotFoundError:
        messages.error(request, 'Attachment file not found on server.')
        return redirect('tasks:task_detail', pk=pk)

@login_required
@require_POST
def remove_attachment_view(request, pk):
    """
    Remove task attachment (HTMX endpoint).
    
    Phase 7B Updates:
    - Uses can_remove_attachment for permission check
    - Returns attachment_section.html partial for HTMX requests
    """
    task = get_object_or_404(Task, pk=pk)
    
    # Phase 7B: Use correct permission check
    if not can_remove_attachment(request.user, task):
        error_msg = 'You do not have permission to remove this attachment.'
        
        if request.headers.get('HX-Request'):
            return HttpResponse(
                f'<div class="text-red-600 text-sm p-2 bg-red-50 rounded">{error_msg}</div>',
                status=403
            )
        messages.error(request, error_msg)
        return redirect('tasks:task_detail', pk=pk)
    
    try:
        remove_attachment(task, request.user)
        
        # HTMX Response: Return updated attachment section (empty state)
        if request.headers.get('HX-Request'):
            return render(request, 'tasks/partials/attachment_section.html', {
                'task': task,
                'attachment': None,
                'attachment_form': AttachmentForm(),
                'can_attachment': can_add_attachment(request.user, task),
                'can_remove': False,  # No attachment to remove anymore
            })
        
        messages.success(request, 'Attachment removed successfully.')
        
    except ValidationError as e:
        error_msg = str(e)
        if request.headers.get('HX-Request'):
            return HttpResponse(
                f'<div class="text-red-600 text-sm p-2 bg-red-50 rounded">{error_msg}</div>',
                status=400
            )
        messages.error(request, error_msg)
        
    except PermissionError as e:
        error_msg = str(e)
        if request.headers.get('HX-Request'):
            return HttpResponse(
                f'<div class="text-red-600 text-sm p-2 bg-red-50 rounded">{error_msg}</div>',
                status=403
            )
        messages.error(request, error_msg)
        
    except Exception as e:
        error_msg = f'Error removing attachment: {str(e)}'
        if request.headers.get('HX-Request'):
            return HttpResponse(
                f'<div class="text-red-600 text-sm p-2 bg-red-50 rounded">{error_msg}</div>',
                status=500
            )
        messages.error(request, error_msg)
    
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
    
    base_qs = Task.objects.exclude(status='cancelled')
    
    counts = {
        'my_personal': base_qs.filter(
            created_by=user, assignee=user, task_type='personal'
        ).count(),
        'assigned_to_me': base_qs.filter(
            assignee=user, task_type='delegated'
        ).count(),
        'i_assigned': base_qs.filter(
            created_by=user, task_type='delegated'
        ).exclude(assignee=user).count(),
    }
    
    return render(request, 'tasks/partials/badge_counts.html', {'counts': counts})


@login_required
def badge_counts(request):
    """JSON endpoint for badge counts (alternative to partial)."""
    return partials_badge_counts(request)


# =============================================================================
# Kanban Views
# =============================================================================

@login_required
def kanban(request):
    """Kanban board view."""
    user = request.user
    
    # Get viewable tasks
    queryset = get_viewable_tasks(user).exclude(status='cancelled')
    
    # Group by status
    columns = {
        'pending': queryset.filter(status='pending').order_by('-priority', 'deadline')[:50],
        'in_progress': queryset.filter(status='in_progress').order_by('-priority', 'deadline')[:50],
        'completed': queryset.filter(status='completed').order_by('-priority', 'deadline')[:50],
        'verified': queryset.filter(status='verified').order_by('-updated_at')[:50],
    }
    
    return render(request, 'tasks/kanban.html', {
        'columns': columns,
        'status_choices': Task.Status.choices,
    })


@login_required
@require_POST
def kanban_move(request, pk):
    """HTMX endpoint for moving task between columns."""
    task = get_object_or_404(Task, pk=pk)
    
    if not can_change_status(request.user, task):
        return HttpResponseForbidden('Permission denied')
    
    new_status = request.POST.get('status')
    if not new_status:
        return HttpResponse('Missing status', status=400)
    
    try:
        change_status(task, request.user, new_status)
        return HttpResponse(status=200)
    except Exception as e:
        return HttpResponse(str(e), status=400)


@login_required
def kanban_column(request, status):
    """Return tasks for a specific kanban column."""
    user = request.user
    
    queryset = get_viewable_tasks(user).filter(
        status=status
    ).exclude(status='cancelled').order_by('-priority', 'deadline')[:50]
    
    return render(request, 'tasks/partials/kanban_column.html', {
        'tasks': queryset,
        'status': status,
    })


# =============================================================================
# Department & Management Views
# =============================================================================

@login_required
def department_tasks(request):
    """Department tasks view (Manager+ only)."""
    user = request.user
    
    # Check role
    if user.role not in ['manager', 'senior_manager_1', 'senior_manager_2', 'admin']:
        messages.error(request, 'You do not have permission to view department tasks.')
        return redirect('tasks:dashboard')
    
    # Get tasks based on role
    if user.role in ['admin', 'senior_manager_1', 'senior_manager_2']:
        # See all departments
        queryset = Task.objects.all()
        departments = Department.objects.all()
    else:
        # Manager sees only their department
        queryset = Task.objects.filter(department=user.department)
        departments = Department.objects.filter(pk=user.department_id) if user.department else Department.objects.none()
    
    # Apply filters
    filter_form = TaskFilter(request.GET, user=user)
    if filter_form.is_valid():
        queryset = filter_form.filter_queryset(queryset)
    
    # Pagination
    paginator = Paginator(queryset.order_by('-created_at'), 20)
    page = request.GET.get('page', 1)
    
    try:
        tasks = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        tasks = paginator.page(1)
    
    return render(request, 'tasks/department_tasks.html', {
        'tasks': tasks,
        'filter_form': filter_form,
        'departments': departments,
    })


@login_required
def management_overview(request):
    """Management overview with stats (Senior Manager+ only)."""
    user = request.user
    
    # Check role
    if user.role not in ['senior_manager_1', 'senior_manager_2', 'admin']:
        messages.error(request, 'You do not have permission to view management overview.')
        return redirect('tasks:dashboard')
    
    # Aggregate stats
    from django.db.models import Count
    
    all_tasks = Task.objects.all()
    
    stats = {
        'total': all_tasks.count(),
        'pending': all_tasks.filter(status='pending').count(),
        'in_progress': all_tasks.filter(status='in_progress').count(),
        'completed': all_tasks.filter(status='completed').count(),
        'verified': all_tasks.filter(status='verified').count(),
        'cancelled': all_tasks.filter(status='cancelled').count(),
        'overdue': all_tasks.filter(
            deadline__lt=timezone.now(),
            status__in=['pending', 'in_progress']
        ).count(),
    }
    
    # Per-department breakdown
    dept_stats = Department.objects.annotate(
        task_count=Count('tasks'),
        pending_count=Count('tasks', filter=Q(tasks__status='pending')),
        overdue_count=Count('tasks', filter=Q(
            tasks__deadline__lt=timezone.now(),
            tasks__status__in=['pending', 'in_progress']
        )),
    ).order_by('name')
    
    # Recent overdue tasks
    overdue_tasks = all_tasks.filter(
        deadline__lt=timezone.now(),
        status__in=['pending', 'in_progress']
    ).select_related('assignee', 'department').order_by('deadline')[:10]
    
    return render(request, 'tasks/management_overview.html', {
        'stats': stats,
        'dept_stats': dept_stats,
        'overdue_tasks': overdue_tasks,
    })