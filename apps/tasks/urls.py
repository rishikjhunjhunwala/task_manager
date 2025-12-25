"""
URL configuration for tasks app.
Will be expanded in Phase 5 (Core Task Management) and Phase 6 (Views & Dashboards).
"""

from django.urls import path
from . import views

app_name = 'tasks'

urlpatterns = [
    # Dashboard (redirects from root URL)
    path('', views.dashboard, name='dashboard'),
    
    # Additional URLs will be added in Phases 5 and 6:
    # path('list/', views.task_list, name='task_list'),
    # path('create/', views.task_create, name='task_create'),
    # path('<int:pk>/', views.task_detail, name='task_detail'),
    # path('<int:pk>/edit/', views.task_edit, name='task_edit'),
    # path('<int:pk>/status/', views.task_status_change, name='task_status_change'),
    # path('kanban/', views.kanban, name='kanban'),
    # path('department/', views.department_tasks, name='department_tasks'),
]
