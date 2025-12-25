"""
Views for activity_log app.
Will be expanded in Phase 8 (Activity Log & Reports).
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test


def is_admin(user):
    """Check if user is an admin."""
    return user.is_authenticated and user.role == 'admin'


@login_required
@user_passes_test(is_admin)
def activity_log_view(request):
    """
    Activity log view (Admin only).
    Placeholder - will be implemented in Phase 8.
    """
    return render(request, 'activity_log/activity_list.html')
