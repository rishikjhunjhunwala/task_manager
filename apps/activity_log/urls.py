"""
URL configuration for activity_log app.

Routes:
- /activity/ - Activity log list (admin only)

Note: HTMX partial routes will be added in a future phase
when live updates are implemented.
"""

from django.urls import path
from . import views

app_name = 'activity_log'

urlpatterns = [
    path('', views.activity_log_view, name='activity_list'),
]