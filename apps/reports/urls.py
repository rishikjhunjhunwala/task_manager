"""
URL patterns for reports app.

Routes:
- /reports/ - Reports dashboard (Manager+ only)
"""

from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # Main reports dashboard
    path('', views.reports_dashboard, name='dashboard'),
]