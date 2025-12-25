"""
Views for departments app.
Will be expanded in Phase 4 (User & Department Management).
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required


# Placeholder views - will be implemented in Phase 4
def placeholder_view(request):
    """Placeholder view for testing."""
    return render(request, 'departments/placeholder.html')
