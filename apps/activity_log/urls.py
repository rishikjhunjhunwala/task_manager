"""
URL configuration for activity_log app.
Will be expanded in Phase 8 (Activity Log & Reports).
"""

from django.urls import path
from . import views

app_name = 'activity_log'

urlpatterns = [
    path('', views.activity_log_view, name='activity_list'),
]
