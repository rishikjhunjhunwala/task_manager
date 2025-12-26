"""
URL configuration for accounts app.

Includes:
- Authentication URLs (login, logout, password change)
- User management URLs (admin only)
- Profile URL
"""

from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('password/change/', views.password_change_view, name='password_change'),
    path('password/change/first-login/', views.password_change_first_login_view, name='password_change_first_login'),
    
    # Profile
    path('profile/', views.profile_view, name='profile'),
    
    # User Management (Admin only)
    path('users/', views.user_list_view, name='user_list'),
    path('users/create/', views.user_create_view, name='user_create'),
    path('users/<int:pk>/edit/', views.user_edit_view, name='user_edit'),
    path('users/<int:pk>/reset-password/', views.user_reset_password_view, name='user_reset_password'),
    path('users/<int:pk>/unlock/', views.user_unlock_view, name='user_unlock'),
    path('users/<int:pk>/deactivate/', views.user_deactivate_view, name='user_deactivate'),
    path('users/<int:pk>/activate/', views.user_activate_view, name='user_activate'),
    
    # HTMX Endpoints
    path('users/<int:pk>/task-warning/', views.user_task_warning_view, name='user_task_warning'),
]
