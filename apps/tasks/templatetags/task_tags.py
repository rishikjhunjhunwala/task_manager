"""
Custom template tags and filters for tasks app.

Phase 6A Implementation:
- 17 filters for task display
- 5 inclusion tags for common components
- URL manipulation helpers for filters
"""

from django import template
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from datetime import timedelta
import urllib.parse

register = template.Library()


# =============================================================================
# Task Status Filters
# =============================================================================

@register.filter
def task_row_class(task):
    """
    Return CSS class for task row based on overdue/escalated status.
    
    Usage: {{ task|task_row_class }}
    """
    if task.status in ['completed', 'verified', 'cancelled']:
        return ''
    
    if task.escalated_to_sm1_at or task.escalated_to_sm2_at:
        return 'task-escalated bg-red-900 text-white'
    
    if task.deadline and timezone.now() > task.deadline:
        return 'task-overdue bg-red-50'
    
    return ''


@register.filter
def priority_border_class(task):
    """
    Return CSS class for left border based on priority.
    
    Usage: {{ task|priority_border_class }}
    """
    priority_classes = {
        'low': 'border-l-4 border-gray-400',
        'medium': 'border-l-4 border-blue-500',
        'high': 'border-l-4 border-amber-500',
        'critical': 'border-l-4 border-red-500',
    }
    return priority_classes.get(task.priority, '')


@register.filter
def status_class(status):
    """
    Return CSS class for status badge.
    
    Usage: {{ task.status|status_class }}
    """
    status_classes = {
        'pending': 'bg-yellow-100 text-yellow-800',
        'in_progress': 'bg-blue-100 text-blue-800',
        'completed': 'bg-green-100 text-green-800',
        'verified': 'bg-emerald-100 text-emerald-800',
        'cancelled': 'bg-gray-100 text-gray-500',
    }
    return status_classes.get(status, 'bg-gray-100 text-gray-800')


@register.filter
def priority_class(priority):
    """
    Return CSS class for priority badge.
    
    Usage: {{ task.priority|priority_class }}
    """
    priority_classes = {
        'low': 'bg-gray-100 text-gray-700',
        'medium': 'bg-blue-100 text-blue-700',
        'high': 'bg-amber-100 text-amber-700',
        'critical': 'bg-red-100 text-red-700',
    }
    return priority_classes.get(priority, 'bg-gray-100 text-gray-700')


@register.filter
def is_overdue(task):
    """
    Check if task is overdue.
    
    Usage: {% if task|is_overdue %}
    """
    if not task.deadline:
        return False
    if task.status in ['completed', 'verified', 'cancelled']:
        return False
    return timezone.now() > task.deadline


@register.filter
def is_escalated(task):
    """
    Check if task has been escalated.
    
    Usage: {% if task|is_escalated %}
    """
    return task.escalated_to_sm1_at is not None or task.escalated_to_sm2_at is not None


@register.filter
def hours_overdue(task):
    """
    Return hours overdue as a number.
    
    Usage: {{ task|hours_overdue }}
    """
    if not task.deadline:
        return 0
    if task.status in ['completed', 'verified', 'cancelled']:
        return 0
    
    now = timezone.now()
    if now <= task.deadline:
        return 0
    
    delta = now - task.deadline
    return delta.total_seconds() / 3600


@register.filter
def hours_overdue_display(task):
    """
    Return human-readable overdue duration.
    
    Usage: {{ task|hours_overdue_display }}
    """
    hours = hours_overdue(task)
    if hours <= 0:
        return ''
    
    if hours < 1:
        minutes = int(hours * 60)
        return f'{minutes}m'
    elif hours < 24:
        return f'{int(hours)}h'
    else:
        days = int(hours / 24)
        remaining_hours = int(hours % 24)
        if remaining_hours > 0:
            return f'{days}d {remaining_hours}h'
        return f'{days}d'


# =============================================================================
# Deadline Filters
# =============================================================================

@register.filter
def format_deadline(deadline):
    """
    Format deadline with relative indicator.
    
    Usage: {{ task.deadline|format_deadline }}
    """
    if not deadline:
        return 'No deadline'
    
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    tomorrow_end = tomorrow_start + timedelta(days=1)
    
    # Check if deadline is today
    if today_start <= deadline < tomorrow_start:
        time_str = deadline.strftime('%I:%M %p').lstrip('0')
        return f'Today, {time_str}'
    
    # Check if deadline is tomorrow
    if tomorrow_start <= deadline < tomorrow_end:
        time_str = deadline.strftime('%I:%M %p').lstrip('0')
        return f'Tomorrow, {time_str}'
    
    # Check if deadline was yesterday
    yesterday_start = today_start - timedelta(days=1)
    if yesterday_start <= deadline < today_start:
        time_str = deadline.strftime('%I:%M %p').lstrip('0')
        return f'Yesterday, {time_str}'
    
    # Otherwise, show full date
    return deadline.strftime('%d %b %Y, %I:%M %p').lstrip('0')


@register.filter
def deadline_relative(deadline):
    """
    Return relative deadline text (e.g., "in 2 days", "3 days ago").
    
    Usage: {{ task.deadline|deadline_relative }}
    """
    if not deadline:
        return ''
    
    now = timezone.now()
    delta = deadline - now
    
    if delta.total_seconds() > 0:
        # Future
        days = delta.days
        hours = delta.seconds // 3600
        
        if days > 7:
            return f'in {days} days'
        elif days > 0:
            return f'in {days}d {hours}h'
        elif hours > 0:
            return f'in {hours}h'
        else:
            minutes = delta.seconds // 60
            return f'in {minutes}m'
    else:
        # Past (overdue)
        delta = now - deadline
        days = delta.days
        hours = delta.seconds // 3600
        
        if days > 7:
            return f'{days} days ago'
        elif days > 0:
            return f'{days}d {hours}h ago'
        elif hours > 0:
            return f'{hours}h ago'
        else:
            minutes = delta.seconds // 60
            return f'{minutes}m ago'


# =============================================================================
# Inclusion Tags (Component Templates)
# =============================================================================

@register.inclusion_tag('tasks/partials/status_badge.html')
def status_badge(task):
    """
    Render a status badge for a task.
    
    Usage: {% status_badge task %}
    """
    return {
        'task': task,
        'status': task.status,
        'status_display': task.get_status_display(),
        'css_class': status_class(task.status),
    }


@register.inclusion_tag('tasks/partials/priority_badge.html')
def priority_badge(priority):
    """
    Render a priority badge.
    
    Usage: {% priority_badge task.priority %}
    """
    display_names = {
        'low': 'Low',
        'medium': 'Medium',
        'high': 'High',
        'critical': 'Critical',
    }
    return {
        'priority': priority,
        'priority_display': display_names.get(priority, priority),
        'css_class': priority_class(priority),
    }


@register.inclusion_tag('tasks/partials/status_dot.html')
def status_dot(status):
    """
    Render a small status indicator dot.
    
    Usage: {% status_dot 'pending' %}
    """
    dot_colors = {
        'pending': 'bg-yellow-400',
        'in_progress': 'bg-blue-400',
        'completed': 'bg-green-400',
        'verified': 'bg-emerald-500',
        'cancelled': 'bg-gray-400',
    }
    return {
        'status': status,
        'color_class': dot_colors.get(status, 'bg-gray-400'),
    }


@register.inclusion_tag('tasks/partials/priority_indicator.html')
def priority_indicator(priority):
    """
    Render a small priority indicator.
    
    Usage: {% priority_indicator 'high' %}
    """
    indicator_colors = {
        'low': 'bg-gray-400',
        'medium': 'bg-blue-500',
        'high': 'bg-amber-500',
        'critical': 'bg-red-500',
    }
    return {
        'priority': priority,
        'color_class': indicator_colors.get(priority, 'bg-gray-400'),
    }


# =============================================================================
# URL Manipulation Tags
# =============================================================================

@register.simple_tag(takes_context=True)
def url_replace(context, field, value):
    """
    Replace or add a query parameter to current URL.
    
    Usage: {% url_replace request 'page' 2 %}
    """
    request = context.get('request')
    if not request:
        return ''
    
    params = request.GET.copy()
    params[field] = value
    return params.urlencode()


@register.simple_tag(takes_context=True)
def remove_filter_param(context, param_name, param_value=''):
    """
    Remove a specific filter parameter from URL.
    For multi-value params (like status), removes just that value.
    
    Usage: {% remove_filter_param 'status' 'pending' %}
    """
    request = context.get('request')
    if not request:
        return ''
    
    params = request.GET.copy()
    
    # Handle multi-value params
    if param_name in params:
        values = params.getlist(param_name)
        if param_value and param_value in values:
            values.remove(param_value)
            if values:
                params.setlist(param_name, values)
            else:
                del params[param_name]
        else:
            del params[param_name]
    
    return params.urlencode()


@register.simple_tag(takes_context=True)
def build_filter_url(context, **kwargs):
    """
    Build URL with filter parameters.
    
    Usage: {% build_filter_url status='pending' priority='high' %}
    """
    request = context.get('request')
    if not request:
        return ''
    
    params = request.GET.copy()
    
    for key, value in kwargs.items():
        if value:
            params[key] = value
        elif key in params:
            del params[key]
    
    query_string = params.urlencode()
    return f'?{query_string}' if query_string else ''


# =============================================================================
# Permission Tags
# =============================================================================

@register.filter
def can_view(user, task):
    """
    Check if user can view the task.
    
    Usage: {% if user|can_view:task %}
    """
    from apps.tasks.permissions import can_view_task
    return can_view_task(user, task)


@register.filter
def can_edit(user, task):
    """
    Check if user can edit the task.
    
    Usage: {% if user|can_edit:task %}
    """
    from apps.tasks.permissions import can_edit_task
    return can_edit_task(user, task)


# =============================================================================
# Simple Output Tags
# =============================================================================

@register.simple_tag
def task_count_badge(count, css_class=''):
    """
    Render a count badge.
    
    Usage: {% task_count_badge 5 'bg-red-500 text-white' %}
    """
    if count == 0:
        return ''
    
    default_class = 'ml-2 py-0.5 px-2.5 rounded-full text-xs font-medium'
    if not css_class:
        css_class = 'bg-gray-100 text-gray-600'
    
    return format_html(
        '<span class="{} {}">{}</span>',
        default_class,
        css_class,
        count
    )
