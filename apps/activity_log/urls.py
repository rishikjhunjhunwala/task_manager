"""
URL configuration for activity_log app.

Routes:
    /activity/         - Main activity log view (admin only)
    /activity/partial/ - Partial view for HTMX updates (Phase 8B)
"""

from django.urls import path
from . import views

app_name = 'activity_log'

urlpatterns = [
    # Main activity log view
    path('', views.activity_log_view, name='activity_list'),
    
    # Partial view for HTMX filtering (Phase 8B)
    path('partial/', views.activity_log_partial, name='activity_partial'),
]