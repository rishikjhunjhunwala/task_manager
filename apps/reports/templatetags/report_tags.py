"""
Template tags and filters for reports app.

Filters:
- hours_overdue: Format hours as "X hours" or "X days, Y hours"
- escalation_level: Return escalation level (1 or 2) based on timestamps
- format_percentage: Format as "X%" with 1 decimal place

Usage:
    {% load report_tags %}
    
    {{ task.hours_overdue|hours_overdue }}
    {{ task|escalation_level }}
    {{ user.completion_rate|format_percentage }}
"""

from django import template

register = template.Library()


@register.filter
def hours_overdue(hours):
    """
    Format hours overdue as a human-readable string.
    
    Args:
        hours: Number of hours (float or int)
        
    Returns:
        str: Formatted string like "5 hours" or "3 days, 12 hours"
        
    Examples:
        5.5 -> "5 hours"
        25.7 -> "1 day, 1 hour"
        72.3 -> "3 days, 0 hours"
        0 -> "0 hours"
    """
    if hours is None:
        return "N/A"
    
    try:
        hours = float(hours)
    except (ValueError, TypeError):
        return "N/A"
    
    if hours < 0:
        return "0 hours"
    
    # Calculate days and remaining hours
    days = int(hours // 24)
    remaining_hours = int(hours % 24)
    
    if days == 0:
        # Less than a day - show hours only
        hour_label = "hour" if remaining_hours == 1 else "hours"
        return f"{int(hours)} {hour_label}"
    else:
        # One or more days
        day_label = "day" if days == 1 else "days"
        hour_label = "hour" if remaining_hours == 1 else "hours"
        return f"{days} {day_label}, {remaining_hours} {hour_label}"


@register.filter
def escalation_level(task_dict):
    """
    Return the escalation level for a task.
    
    Args:
        task_dict: Dictionary containing task data with escalation timestamps
                   OR a Task model instance
        
    Returns:
        int: 1 (72h escalation) or 2 (120h escalation) or 0 (not escalated)
        
    Level 1: Only escalated_to_sm2_at is set (72h overdue)
    Level 2: escalated_to_sm1_at is also set (120h overdue)
    """
    if task_dict is None:
        return 0
    
    # Handle both dict and model instance
    if isinstance(task_dict, dict):
        escalated_to_sm1 = task_dict.get('escalated_to_sm1_at')
        escalated_to_sm2 = task_dict.get('escalated_to_sm2_at')
    else:
        # Assume it's a Task model instance
        escalated_to_sm1 = getattr(task_dict, 'escalated_to_sm1_at', None)
        escalated_to_sm2 = getattr(task_dict, 'escalated_to_sm2_at', None)
    
    if escalated_to_sm1:
        return 2  # 120h+ overdue - escalated to SM1
    elif escalated_to_sm2:
        return 1  # 72h+ overdue - escalated to SM2
    else:
        return 0  # Not escalated


@register.filter
def format_percentage(value, decimal_places=1):
    """
    Format a number as a percentage with specified decimal places.
    
    Args:
        value: Number to format (already as percentage, e.g., 85.5 for 85.5%)
        decimal_places: Number of decimal places (default 1)
        
    Returns:
        str: Formatted percentage like "85.5%"
        
    Examples:
        85.555 -> "85.6%"
        100 -> "100.0%"
        0 -> "0.0%"
        None -> "0.0%"
    """
    if value is None:
        return "0.0%"
    
    try:
        value = float(value)
    except (ValueError, TypeError):
        return "0.0%"
    
    # Format with specified decimal places
    try:
        decimal_places = int(decimal_places)
    except (ValueError, TypeError):
        decimal_places = 1
    
    return f"{value:.{decimal_places}f}%"


@register.filter
def escalation_badge_class(level):
    """
    Return CSS class for escalation level badge.
    
    Args:
        level: Escalation level (0, 1, or 2)
        
    Returns:
        str: CSS class string for Tailwind
    """
    if level == 2:
        return "bg-red-800 text-white"  # Critical - Level 2 (120h+)
    elif level == 1:
        return "bg-red-600 text-white"  # Warning - Level 1 (72h+)
    else:
        return "bg-gray-100 text-gray-800"  # Not escalated


@register.filter
def overdue_severity_class(hours):
    """
    Return CSS class based on how overdue a task is.
    
    Args:
        hours: Number of hours overdue
        
    Returns:
        str: CSS class string for Tailwind background
    """
    if hours is None:
        return ""
    
    try:
        hours = float(hours)
    except (ValueError, TypeError):
        return ""
    
    if hours >= 120:
        return "bg-red-100"  # Critical - 5+ days
    elif hours >= 72:
        return "bg-orange-100"  # Severe - 3+ days
    elif hours >= 24:
        return "bg-yellow-100"  # Warning - 1+ days
    else:
        return "bg-amber-50"  # Minor - less than 1 day


@register.simple_tag
def get_escalation_label(level):
    """
    Return human-readable label for escalation level.
    
    Args:
        level: Escalation level (0, 1, or 2)
        
    Returns:
        str: Label like "Level 1 (72h+)" or "Level 2 (120h+)"
    """
    if level == 2:
        return "Level 2 (120h+)"
    elif level == 1:
        return "Level 1 (72h+)"
    else:
        return "Not Escalated"