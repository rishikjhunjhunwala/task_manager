"""
Views for tasks app.
Will be expanded in Phase 5 (Core Task Management) and Phase 6 (Views & Dashboards).
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required


@login_required
def dashboard(request):
    """
    Main dashboard view.
    Placeholder - will be implemented in Phase 6.
    """
    return render(request, 'tasks/dashboard.html')


# Additional views will be added in Phases 5 and 6:
# - task_list
# - task_create
# - task_detail
# - task_edit
# - task_status_change
# - kanban
# - department_tasks
# - kanban_move
