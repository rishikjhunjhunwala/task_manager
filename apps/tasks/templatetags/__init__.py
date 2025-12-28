"""
Template tags package for tasks app.

Provides custom template tags and filters for task display:
- is_overdue: Check if task is past deadline
- is_escalated: Check if task is 72+ hours overdue
- format_deadline: Format deadline with relative time
- status_class: Return CSS class for task status
- priority_class: Return CSS class for task priority
- hours_overdue: Calculate hours past deadline
- task_row_class: Return combined CSS classes for task row styling
"""
