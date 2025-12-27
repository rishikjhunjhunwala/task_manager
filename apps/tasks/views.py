"""
Views for tasks app.

Task management views including:
- Dashboard with tabs
- Task list view
- Task create/edit
- Task detail
- Status changes
- Reassignment
- Cancellation
- Comments (HTMX)
- Attachments
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden, FileResponse, Http404
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone

from .models import Task, Comment, Attachment
from .forms import (
    TaskForm, TaskEditForm, ReassignTaskForm, CancelTaskForm,
    StatusChangeForm, CommentForm, AttachmentForm
)
from .services import (
    create_task, update_task, change_status, reassign_task,
    cancel_task, add_comment, add_or_replace_attachment, delete_attachment,
    get_tasks_for_user, get_task_counts
)
from .permissions import (
    can_view_task, can_edit_task, can_change_status,
    can_reassign_task, can_cancel_task, can_add_comment, can_add_attachment, require_task_permission
)


@login_required
def dashboard(request):
    """
    Main dashboard view with tabs:
    - My Personal Tasks
    - Assigned to Me
    - I Assigned
    """
    tab = request.GET.get('tab', 'assigned_to_me')
    valid_tabs = ['my_personal', 'assigned_to_me', 'i_assigned']
    if tab not in valid_tabs:
        tab = 'assigned_to_me'
    
    # Get tasks for current tab
    tasks = get_tasks_for_user(request.user, tab)
    
    # Apply sorting
    sort = request.GET.get('sort', '-created_at')
    valid_sorts = ['deadline', '-deadline', 'created_at', '-created_at', 'priority', '-priority', 'status', '-status']
    if sort not in valid_sorts:
        sort = '-created_at'
    
    # Special handling for priority sort (custom order)
    if sort in ['priority', '-priority']:
        from django.db.models import Case, When, Value, IntegerField
        priority_order = Case(
            When(priority='critical', then=Value(1)),
            When(priority='high', then=Value(2)),
            When(priority='medium', then=Value(3)),
            When(priority='low', then=Value(4)),
            output_field=IntegerField(),
        )
        if sort == '-priority':
            tasks = tasks.annotate(priority_order=priority_order).order_by('priority_order')
        else:
            tasks = tasks.annotate(priority_order=priority_order).order_by('-priority_order')
    else:
        tasks = tasks.order_by(sort)
    
    # Apply filters
    status_filter = request.GET.get('status', '')
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    
    priority_filter = request.GET.get('priority', '')
    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)
    
    # Search
    search = request.GET.get('search', '').strip()
    if search:
        tasks = tasks.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(reference_number__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(tasks, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get counts for badges
    counts = get_task_counts(request.user)
    
    context = {
        'tab': tab,
        'page_obj': page_obj,
        'counts': counts,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'search': search,
        'sort': sort,
        'status_choices': Task.Status.choices,
        'priority_choices': Task.Priority.choices,
    }
    
    # Handle HTMX partial request
    if request.htmx:
        return render(request, 'tasks/partials/task_list.html', context)
    
    return render(request, 'tasks/dashboard.html', context)


@login_required
def task_create(request):
    """Create a new task."""
    if request.method == 'POST':
        form = TaskForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                task = create_task(
                    title=form.cleaned_data['title'],
                    assignee=form.cleaned_data['assignee'],
                    created_by=request.user,
                    description=form.cleaned_data.get('description', ''),
                    deadline=form.cleaned_data.get('deadline'),
                    priority=form.cleaned_data.get('priority', 'medium'),
                )
                messages.success(
                    request,
                    f'Task "{task.reference_number}" created successfully.'
                )
                return redirect('tasks:task_detail', pk=task.pk)
            except Exception as e:
                messages.error(request, str(e))
    else:
        form = TaskForm(user=request.user)
    
    return render(request, 'tasks/task_form.html', {
        'form': form,
        'title': 'Create Task',
        'submit_text': 'Create Task',
    })


@login_required
def task_detail(request, pk):
    """View task details."""
    task = get_object_or_404(
        Task.objects.select_related('assignee', 'created_by', 'department', 'cancelled_by'),
        pk=pk
    )
    
    # Check view permission
    if not can_view_task(request.user, task):
        messages.error(request, "You don't have permission to view this task.")
        return redirect('tasks:dashboard')
    
    # Get comments
    comments = task.comments.select_related('author').order_by('created_at')
    
    # Get attachment if exists
    try:
        attachment = task.attachment
    except Attachment.DoesNotExist:
        attachment = None
    
    # Get activity log (last 10 entries)
    activities = task.activities.select_related('user').order_by('-created_at')[:10]
    
    # Prepare forms
    comment_form = CommentForm()
    attachment_form = AttachmentForm()
    status_form = StatusChangeForm(task=task, user=request.user)
    
    # Check permissions for action buttons
    context = {
        'task': task,
        'comments': comments,
        'attachment': attachment,
        'activities': activities,
        'comment_form': comment_form,
        'attachment_form': attachment_form,
        'status_form': status_form,
        'can_edit': can_edit_task(request.user, task),
        'can_change_status': can_change_status(request.user, task),
        'can_reassign': can_reassign_task(request.user, task),
        'can_cancel': can_cancel_task(request.user, task),
        'can_comment': can_add_comment(request.user, task),
        'can_attach': can_add_attachment(request.user, task),
    }
    
    return render(request, 'tasks/task_detail.html', context)


@login_required
def task_edit(request, pk):
    """Edit an existing task."""
    task = get_object_or_404(Task, pk=pk)
    
    # Check edit permission
    if not can_edit_task(request.user, task):
        messages.error(request, "You don't have permission to edit this task.")
        return redirect('tasks:task_detail', pk=pk)
    
    if request.method == 'POST':
        form = TaskEditForm(request.POST, instance=task)
        if form.is_valid():
            try:
                update_task(
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
                messages.error(request, str(e))
    else:
        form = TaskEditForm(instance=task)
    
    return render(request, 'tasks/task_form.html', {
        'form': form,
        'task': task,
        'title': f'Edit Task: {task.reference_number}',
        'submit_text': 'Save Changes',
    })


@login_required
@require_POST
def task_status_change(request, pk):
    """Change task status."""
    task = get_object_or_404(Task, pk=pk)
    
    # Check permission
    if not can_change_status(request.user, task):
        messages.error(request, "You don't have permission to change this task's status.")
        return redirect('tasks:task_detail', pk=pk)
    
    form = StatusChangeForm(request.POST, task=task, user=request.user)
    if form.is_valid():
        try:
            change_status(task, request.user, form.cleaned_data['new_status'])
            new_status_display = dict(Task.Status.choices).get(form.cleaned_data['new_status'])
            messages.success(request, f'Task status changed to "{new_status_display}".')
        except Exception as e:
            messages.error(request, str(e))
    else:
        for error in form.errors.values():
            messages.error(request, error)
    
    # Handle HTMX request
    if request.htmx:
        return redirect('tasks:task_detail', pk=pk)
    
    return redirect('tasks:task_detail', pk=pk)


@login_required
def task_reassign(request, pk):
    """Reassign task to a different user."""
    task = get_object_or_404(Task, pk=pk)
    
    # Check permission
    if not can_reassign_task(request.user, task):
        messages.error(request, "You don't have permission to reassign this task.")
        return redirect('tasks:task_detail', pk=pk)
    
    if request.method == 'POST':
        form = ReassignTaskForm(request.POST, user=request.user, task=task)
        if form.is_valid():
            try:
                reassign_task(task, request.user, form.cleaned_data['new_assignee'])
                messages.success(
                    request,
                    f'Task reassigned to {form.cleaned_data["new_assignee"].get_full_name()}.'
                )
                return redirect('tasks:task_detail', pk=pk)
            except Exception as e:
                messages.error(request, str(e))
    else:
        form = ReassignTaskForm(user=request.user, task=task)
    
    return render(request, 'tasks/task_reassign.html', {
        'form': form,
        'task': task,
    })


@login_required
def task_cancel(request, pk):
    """Cancel a task."""
    task = get_object_or_404(Task, pk=pk)
    
    # Check permission
    if not can_cancel_task(request.user, task):
        messages.error(request, "You don't have permission to cancel this task.")
        return redirect('tasks:task_detail', pk=pk)
    
    if request.method == 'POST':
        form = CancelTaskForm(request.POST)
        if form.is_valid():
            try:
                cancel_task(task, request.user, form.cleaned_data.get('reason'))
                messages.success(request, 'Task cancelled successfully.')
                return redirect('tasks:dashboard')
            except Exception as e:
                messages.error(request, str(e))
    else:
        form = CancelTaskForm()
    
    return render(request, 'tasks/task_cancel.html', {
        'form': form,
        'task': task,
    })


@login_required
@require_POST
def add_comment_view(request, pk):
    """Add a comment to a task (HTMX endpoint)."""
    task = get_object_or_404(Task, pk=pk)
    
    # Check permission
    if not can_add_comment(request.user, task):
        return HttpResponseForbidden("You cannot add comments to this task.")
    
    form = CommentForm(request.POST)
    if form.is_valid():
        try:
            comment = add_comment(task, request.user, form.cleaned_data['content'])
            
            if request.htmx:
                # Return just the new comment for HTMX append
                return render(request, 'tasks/partials/comment.html', {
                    'comment': comment,
                })
            
            messages.success(request, 'Comment added.')
        except Exception as e:
            if request.htmx:
                return HttpResponse(f'<p class="text-red-600">{str(e)}</p>')
            messages.error(request, str(e))
    else:
        if request.htmx:
            return HttpResponse('<p class="text-red-600">Comment cannot be empty.</p>')
        messages.error(request, 'Comment cannot be empty.')
    
    return redirect('tasks:task_detail', pk=pk)


@login_required
@require_POST
def upload_attachment(request, pk):
    """Upload or replace task attachment."""
    task = get_object_or_404(Task, pk=pk)
    
    # Check permission
    if not can_add_attachment(request.user, task):
        messages.error(request, "You don't have permission to add attachments.")
        return redirect('tasks:task_detail', pk=pk)
    
    form = AttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            add_or_replace_attachment(task, request.user, form.cleaned_data['file'])
            messages.success(request, 'Attachment uploaded successfully.')
        except Exception as e:
            messages.error(request, str(e))
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, error)
    
    return redirect('tasks:task_detail', pk=pk)


@login_required
@require_POST
def remove_attachment(request, pk):
    """Remove task attachment."""
    task = get_object_or_404(Task, pk=pk)
    
    # Check permission
    if not can_add_attachment(request.user, task):
        messages.error(request, "You don't have permission to remove attachments.")
        return redirect('tasks:task_detail', pk=pk)
    
    try:
        delete_attachment(task, request.user)
        messages.success(request, 'Attachment removed.')
    except Exception as e:
        messages.error(request, str(e))
    
    return redirect('tasks:task_detail', pk=pk)


@login_required
@require_GET
def download_attachment(request, pk):
    """Download task attachment."""
    task = get_object_or_404(Task, pk=pk)
    
    # Check view permission
    if not can_view_task(request.user, task):
        raise Http404("Attachment not found.")
    
    try:
        attachment = task.attachment
    except Attachment.DoesNotExist:
        raise Http404("Attachment not found.")
    
    # Serve file
    response = FileResponse(
        attachment.file.open('rb'),
        as_attachment=True,
        filename=attachment.filename
    )
    return response


# =============================================================================
# HTMX Partial Views
# =============================================================================

@login_required
def task_list_partial(request):
    """
    Return task list partial for HTMX updates.
    Used for filtering, sorting, pagination without full page reload.
    """
    return dashboard(request)


@login_required
def task_row_partial(request, pk):
    """Return single task row partial for HTMX updates."""
    task = get_object_or_404(Task, pk=pk)
    
    if not can_view_task(request.user, task):
        return HttpResponse('')
    
    return render(request, 'tasks/partials/task_row.html', {'task': task})


@login_required
def task_counts_partial(request):
    """Return task counts for badge updates (HTMX polling)."""
    counts = get_task_counts(request.user)
    return render(request, 'tasks/partials/badge_counts.html', {'counts': counts})


# =============================================================================
# Quick Status Change (HTMX inline button)
# =============================================================================

@login_required
@require_POST
def quick_status_change(request, pk):
    """
    Quick status change via inline button.
    Advances task to next logical status.
    """
    task = get_object_or_404(Task, pk=pk)
    
    if not can_change_status(request.user, task):
        if request.htmx:
            return HttpResponse(
                '<span class="text-red-600 text-sm">Permission denied</span>'
            )
        messages.error(request, "You don't have permission to change this task's status.")
        return redirect('tasks:task_detail', pk=pk)
    
    next_status = task.get_next_status()
    if not next_status:
        if request.htmx:
            return HttpResponse(
                '<span class="text-gray-600 text-sm">No further actions</span>'
            )
        messages.info(request, "No further status changes available.")
        return redirect('tasks:task_detail', pk=pk)
    
    try:
        change_status(task, request.user, next_status)
        
        if request.htmx:
            # Return updated status button
            task.refresh_from_db()
            return render(request, 'tasks/partials/status_button.html', {
                'task': task,
                'can_change_status': can_change_status(request.user, task),
            })
        
        messages.success(
            request,
            f'Task status changed to "{task.get_status_display()}".'
        )
    except Exception as e:
        if request.htmx:
            return HttpResponse(f'<span class="text-red-600 text-sm">{str(e)}</span>')
        messages.error(request, str(e))
    
    return redirect('tasks:task_detail', pk=pk)
