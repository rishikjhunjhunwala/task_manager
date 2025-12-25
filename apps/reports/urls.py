"""
URL configuration for reports app.
Will be expanded in Phase 8 (Activity Log & Reports).
"""

from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.reports_view, name='reports'),
]
