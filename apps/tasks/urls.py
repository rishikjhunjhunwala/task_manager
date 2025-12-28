"""
URL configuration for tasks app.

Includes:
- Dashboard
- Task list with filters
- Task CRUD operations
- Status changes
- Comments and attachments
- HTMX partials
"""

from django.urls import path
from . import views

app_name = 'tasks'

urlpatterns = [
    # Dashboard (main view)
    path('', views.dashboard, name='dashboard'),
    
    # Task List (full filtered view)
    path('list/', views.task_list, name='task_list'),
    
    # Task CRUD
    path('create/', views.task_create, name='task_create'),
    path('<int:pk>/', views.task_detail, name='task_detail'),
    path('<int:pk>/edit/', views.task_edit, name='task_edit'),
    
    # Status changes
    path('<int:pk>/status/', views.task_status_change, name='task_status_change'),
    path('<int:pk>/quick-status/', views.quick_status_change, name='quick_status_change'),
    
    # Task actions
    path('<int:pk>/reassign/', views.task_reassign, name='task_reassign'),
    path('<int:pk>/cancel/', views.task_cancel, name='task_cancel'),
    
    # Comments
    path('<int:pk>/comment/', views.add_comment_view, name='add_comment'),
    
    # Attachments
    path('<int:pk>/attachment/', views.upload_attachment, name='upload_attachment'),
    path('<int:pk>/attachment/download/', views.download_attachment, name='download_attachment'),
    path('<int:pk>/attachment/remove/', views.remove_attachment_view, name='remove_attachment'),
    
    # HTMX Partials
    path('partials/task/<int:pk>/', views.partials_task_row, name='partials_task_row'),
    path('partials/counts/', views.partials_badge_counts, name='partials_badge_counts'),
]
