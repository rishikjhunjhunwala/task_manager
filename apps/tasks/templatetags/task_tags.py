"""
Custom template tags and filters for tasks app.

Usage in templates:
    {% load task_tags %}
    
    {# Filters #}
    {{ task|is_overdue }}
    {{ task|is_escalated }}
    {{ task|hours_overdue }}
    {{ task.deadline|format_deadline }}
    {{ task.status|status_class }}
    {{ task.priority|priority_class }}
    {{ task|task_row_class }}
    
    {# Tags #}
    {% overdue_badge task %}
    {% priority_badge task %}
    {% status_badge task %}
"""

from django import template
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from datetime import timedelta

register = template.Library()


# =============================================================================
# FILTERS - Task Property Checks
# =============================================================================

@register.filter
def is_overdue(task):
    """
    Check if a task is overdue.
    
    Returns True if:
    - Task has a deadline
    - Deadline is in the past
    - Task is not completed, verified, or cancelled
    
    Usage: {{ task|is_overdue }}
    """
    if not task:
        return False
    
    # Use the model's property if available
    if hasattr(task, 'is_overdue'):
        return task.is_overdue
    
    # Fallback calculation
    if not task.deadline:
        return False
    
    if task.status in ['completed', 'verified', 'cancelled']:
        return False
    
    return timezone.now() > task.deadline


@register.filter
def is_escalated(task):
    """
    Check if a task is escalated (72+ hours overdue).
    
    Returns True if:
    - Task has been escalated to SM2 or SM1
    - OR task is 72+ hours overdue
    
    Usage: {{ task|is_escalated }}
    """
    if not task:
        return False
    
    # Use the model's property if available
    if hasattr(task, 'is_escalated'):
        return task.is_escalated
    
    # Fallback: check escalation timestamps
    if task.escalated_to_sm2_at or task.escalated_to_sm1_at:
        return True
    
    # Fallback: check if 72+ hours overdue
    overdue_hours = hours_overdue(task)
    return overdue_hours >= 72


@register.filter
def hours_overdue(task):
    """
    Calculate hours past deadline.
    
    Returns:
    - 0 if task is not overdue
    - Number of hours overdue (float) if overdue
    
    Usage: {{ task|hours_overdue }}
    """
    if not task:
        return 0
    
    # Use the model's property if available
    if hasattr(task, 'hours_overdue'):
        return task.hours_overdue
    
    # Fallback calculation
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
    Return hours overdue as a formatted string.
    
    Usage: {{ task|hours_overdue_display }}
    """
    hours = hours_overdue(task)
    if hours == 0:
        return ""
    
    if hours < 1:
        minutes = int(hours * 60)
        return f"{minutes} min overdue"
    elif hours < 24:
        return f"{int(hours)} hr overdue"
    else:
        days = int(hours / 24)
        remaining_hours = int(hours % 24)
        if remaining_hours > 0:
            return f"{days}d {remaining_hours}h overdue"
        return f"{days} days overdue"


# =============================================================================
# FILTERS - Deadline Formatting
# =============================================================================

@register.filter
def format_deadline(deadline):
    """
    Format deadline with relative time indication.
    
    Examples:
    - "Today, 5:00 PM"
    - "Tomorrow, 9:00 AM"
    - "In 2 days (Dec 30)"
    - "3 days ago (Dec 25)" - for overdue
    - "Next week (Jan 2)"
    
    Usage: {{ task.deadline|format_deadline }}
    """
    if not deadline:
        return "No deadline"
    
    now = timezone.now()
    today = now.date()
    deadline_date = deadline.date()
    time_str = deadline.strftime("%-I:%M %p")  # 5:00 PM format
    
    # Calculate difference in days
    delta_days = (deadline_date - today).days
    
    if delta_days == 0:
        return f"Today, {time_str}"
    elif delta_days == 1:
        return f"Tomorrow, {time_str}"
    elif delta_days == -1:
        return f"Yesterday, {time_str}"
    elif delta_days < -1:
        # Overdue
        abs_days = abs(delta_days)
        date_str = deadline.strftime("%b %-d")
        if abs_days < 7:
            return f"{abs_days} days ago ({date_str})"
        elif abs_days < 30:
            weeks = abs_days // 7
            return f"{weeks} week{'s' if weeks > 1 else ''} ago ({date_str})"
        else:
            return f"Overdue ({date_str})"
    elif delta_days <= 7:
        # Within a week
        date_str = deadline.strftime("%b %-d")
        return f"In {delta_days} days ({date_str})"
    elif delta_days <= 14:
        date_str = deadline.strftime("%b %-d")
        return f"Next week ({date_str})"
    else:
        # More than 2 weeks away
        date_str = deadline.strftime("%b %-d, %Y")
        return date_str


@register.filter
def deadline_short(deadline):
    """
    Short deadline format for list views.
    
    Examples:
    - "Today 5PM"
    - "Dec 30"
    - "Jan 2, 2026"
    
    Usage: {{ task.deadline|deadline_short }}
    """
    if not deadline:
        return "—"
    
    now = timezone.now()
    today = now.date()
    deadline_date = deadline.date()
    
    if deadline_date == today:
        return deadline.strftime("Today %-I%p")
    elif deadline_date.year == today.year:
        return deadline.strftime("%b %-d")
    else:
        return deadline.strftime("%b %-d, %Y")


# =============================================================================
# FILTERS - CSS Class Generation
# =============================================================================

@register.filter
def status_class(status):
    """
    Return CSS class for task status.
    
    Maps status values to CSS classes defined in main.css:
    - pending → status-pending (yellow)
    - in_progress → status-in-progress (blue)
    - completed → status-completed (green)
    - verified → status-verified (bright green)
    - cancelled → status-cancelled (gray)
    
    Usage: {{ task.status|status_class }}
    """
    status_classes = {
        'pending': 'status-pending',
        'in_progress': 'status-in-progress',
        'completed': 'status-completed',
        'verified': 'status-verified',
        'cancelled': 'status-cancelled',
    }
    return status_classes.get(status, '')


@register.filter
def priority_class(priority):
    """
    Return CSS class for task priority.
    
    Maps priority values to CSS classes defined in main.css:
    - low → priority-low (gray left border)
    - medium → priority-medium (blue left border)
    - high → priority-high (amber left border)
    - critical → priority-critical (red left border)
    
    Usage: {{ task.priority|priority_class }}
    """
    priority_classes = {
        'low': 'priority-low',
        'medium': 'priority-medium',
        'high': 'priority-high',
        'critical': 'priority-critical',
    }
    return priority_classes.get(priority, '')


@register.filter
def task_row_class(task):
    """
    Return combined CSS classes for a task row.
    
    Combines:
    - Priority class (left border color)
    - Overdue class (red background) if applicable
    - Escalated class (maroon background) if applicable
    
    Escalated takes precedence over overdue for background.
    
    Usage: <tr class="{{ task|task_row_class }}">
    """
    if not task:
        return ''
    
    classes = []
    
    # Priority class (always applied for left border)
    if task.priority:
        classes.append(priority_class(task.priority))
    
    # Check escalated first (takes precedence over overdue)
    if is_escalated(task):
        classes.append('task-escalated')
    elif is_overdue(task):
        classes.append('task-overdue')
    
    return ' '.join(classes)


@register.filter
def task_card_class(task):
    """
    Return CSS classes for a Kanban card.
    
    Similar to task_row_class but optimized for card display.
    
    Usage: <div class="kanban-card {{ task|task_card_class }}">
    """
    return task_row_class(task)


# =============================================================================
# FILTERS - Status Display
# =============================================================================

@register.filter
def status_display(status):
    """
    Return human-readable status label.
    
    Usage: {{ task.status|status_display }}
    """
    status_labels = {
        'pending': 'Pending',
        'in_progress': 'In Progress',
        'completed': 'Completed',
        'verified': 'Verified',
        'cancelled': 'Cancelled',
    }
    return status_labels.get(status, status)


@register.filter
def priority_display(priority):
    """
    Return human-readable priority label.
    
    Usage: {{ task.priority|priority_display }}
    """
    priority_labels = {
        'low': 'Low',
        'medium': 'Medium',
        'high': 'High',
        'critical': 'Critical',
    }
    return priority_labels.get(priority, priority)


# =============================================================================
# SIMPLE TAGS - Badge Generation
# =============================================================================

@register.simple_tag
def overdue_badge(task):
    """
    Generate HTML badge for overdue/escalated status.
    
    Returns:
    - Empty string if not overdue
    - Red "OVERDUE" badge if overdue
    - Maroon "ESCALATED" badge if 72+ hours overdue
    
    Usage: {% overdue_badge task %}
    """
    if not task:
        return ''
    
    if is_escalated(task):
        hours = hours_overdue(task)
        level = "Level 2" if task.escalated_to_sm1_at else "Level 1"
        return format_html(
            '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium '
            'bg-red-900 text-white" title="{} hours overdue - {}">'
            'ESCALATED</span>',
            int(hours), level
        )
    elif is_overdue(task):
        hours = hours_overdue(task)
        return format_html(
            '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium '
            'bg-red-100 text-red-800" title="{} hours overdue">'
            'OVERDUE</span>',
            int(hours)
        )
    
    return ''


@register.simple_tag
def priority_badge(task):
    """
    Generate HTML badge for task priority.
    
    Usage: {% priority_badge task %}
    """
    if not task or not task.priority:
        return ''
    
    colors = {
        'low': 'bg-gray-100 text-gray-800',
        'medium': 'bg-blue-100 text-blue-800',
        'high': 'bg-amber-100 text-amber-800',
        'critical': 'bg-red-100 text-red-800',
    }
    
    color_class = colors.get(task.priority, 'bg-gray-100 text-gray-800')
    label = priority_display(task.priority)
    
    return format_html(
        '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium {}">'
        '{}</span>',
        color_class, label
    )


@register.simple_tag
def status_badge(task):
    """
    Generate HTML badge for task status.
    
    Usage: {% status_badge task %}
    """
    if not task or not task.status:
        return ''
    
    colors = {
        'pending': 'bg-yellow-100 text-yellow-800',
        'in_progress': 'bg-blue-100 text-blue-800',
        'completed': 'bg-green-100 text-green-800',
        'verified': 'bg-green-200 text-green-900',
        'cancelled': 'bg-gray-100 text-gray-800',
    }
    
    color_class = colors.get(task.status, 'bg-gray-100 text-gray-800')
    label = status_display(task.status)
    
    return format_html(
        '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium {}">'
        '{}</span>',
        color_class, label
    )


@register.simple_tag
def task_type_badge(task):
    """
    Generate HTML badge for task type (personal/delegated).
    
    Usage: {% task_type_badge task %}
    """
    if not task:
        return ''
    
    if task.task_type == 'personal':
        return format_html(
            '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium '
            'bg-purple-100 text-purple-800">Personal</span>'
        )
    else:
        return format_html(
            '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium '
            'bg-indigo-100 text-indigo-800">Delegated</span>'
        )


# =============================================================================
# INCLUSION TAGS - Complex HTML Components
# =============================================================================

@register.inclusion_tag('tasks/partials/deadline_display.html')
def deadline_display(task):
    """
    Render deadline with appropriate styling and icons.
    
    Usage: {% deadline_display task %}
    
    Requires template: templates/tasks/partials/deadline_display.html
    """
    return {
        'task': task,
        'is_overdue': is_overdue(task),
        'is_escalated': is_escalated(task),
        'formatted_deadline': format_deadline(task.deadline) if task.deadline else None,
        'hours_overdue': hours_overdue(task),
    }


# =============================================================================
# UTILITY FILTERS
# =============================================================================

@register.filter
def can_edit(task, user):
    """
    Check if user can edit the task.
    
    Usage: {% if task|can_edit:request.user %}
    """
    if not task or not user:
        return False
    
    # Import here to avoid circular imports
    from apps.tasks.permissions import can_edit_task
    return can_edit_task(user, task)


@register.filter
def can_change_status(task, user):
    """
    Check if user can change task status.
    
    Usage: {% if task|can_change_status:request.user %}
    """
    if not task or not user:
        return False
    
    from apps.tasks.permissions import can_change_task_status
    return can_change_task_status(user, task)


@register.filter
def escalation_level(task):
    """
    Return escalation level as integer (0, 1, or 2).
    
    0 = Not escalated
    1 = 72+ hours (SM2)
    2 = 120+ hours (SM1)
    
    Usage: {{ task|escalation_level }}
    """
    if not task:
        return 0
    
    if hasattr(task, 'escalation_level'):
        return task.escalation_level
    
    if task.escalated_to_sm1_at:
        return 2
    if task.escalated_to_sm2_at:
        return 1
    return 0


@register.filter
def next_status(task):
    """
    Return the next logical status for a task.
    
    Usage: {{ task|next_status }}
    """
    if not task:
        return None
    
    if hasattr(task, 'get_next_status'):
        return task.get_next_status()
    
    status_flow = {
        'pending': 'in_progress',
        'in_progress': 'completed',
        'completed': 'verified' if task.task_type == 'delegated' else None,
    }
    return status_flow.get(task.status)


@register.filter
def next_status_display(task):
    """
    Return display text for next status button.
    
    Usage: {{ task|next_status_display }}
    """
    next_stat = next_status(task)
    if not next_stat:
        return None
    
    labels = {
        'in_progress': 'Start Working',
        'completed': 'Mark Complete',
        'verified': 'Verify Task',
    }
    return labels.get(next_stat, next_stat)
