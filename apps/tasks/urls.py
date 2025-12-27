"""
URL configuration for tasks app.

URL Patterns:
- / - Dashboard (default)
- /create/ - Create new task
- /<pk>/ - Task detail
- /<pk>/edit/ - Edit task
- /<pk>/status/ - Change status (POST)
- /<pk>/quick-status/ - Quick status change (HTMX POST)
- /<pk>/reassign/ - Reassign task
- /<pk>/cancel/ - Cancel task
- /<pk>/comment/ - Add comment (POST)
- /<pk>/attachment/ - Upload attachment (POST)
- /<pk>/attachment/download/ - Download attachment
- /<pk>/attachment/remove/ - Remove attachment (POST)

HTMX Partials:
- /partials/list/ - Task list partial
- /partials/task/<pk>/ - Single task row
- /partials/counts/ - Badge counts
"""

from django.urls import path
from . import views

app_name = 'tasks'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Task CRUD
    path('create/', views.task_create, name='task_create'),
    path('<int:pk>/', views.task_detail, name='task_detail'),
    path('<int:pk>/edit/', views.task_edit, name='task_edit'),
    
    # Status management
    path('<int:pk>/status/', views.task_status_change, name='task_status_change'),
    path('<int:pk>/quick-status/', views.quick_status_change, name='quick_status_change'),
    
    # Reassignment and cancellation
    path('<int:pk>/reassign/', views.task_reassign, name='task_reassign'),
    path('<int:pk>/cancel/', views.task_cancel, name='task_cancel'),
    
    # Comments
    path('<int:pk>/comment/', views.add_comment_view, name='add_comment'),
    
    # Attachments
    path('<int:pk>/attachment/', views.upload_attachment, name='upload_attachment'),
    path('<int:pk>/attachment/download/', views.download_attachment, name='download_attachment'),
    path('<int:pk>/attachment/remove/', views.remove_attachment, name='remove_attachment'),
    
    # HTMX Partials
    path('partials/list/', views.task_list_partial, name='task_list_partial'),
    path('partials/task/<int:pk>/', views.task_row_partial, name='task_row_partial'),
    path('partials/counts/', views.task_counts_partial, name='task_counts_partial'),
]
