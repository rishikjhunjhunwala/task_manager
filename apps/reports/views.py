"""
Views for reports app.
Will be expanded in Phase 8 (Activity Log & Reports).
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test


def is_manager_or_above(user):
    """Check if user is Manager or higher."""
    return user.is_authenticated and user.role in [
        'admin', 'senior_manager_1', 'senior_manager_2', 'manager'
    ]


@login_required
@user_passes_test(is_manager_or_above)
def reports_view(request):
    """
    Reports dashboard (Manager+ only).
    Placeholder - will be implemented in Phase 8.
    """
    return render(request, 'reports/reports.html')
