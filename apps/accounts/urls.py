"""
URL configuration for accounts app.

Phase 3: Authentication & Security URLs including:
- Login
- Logout
- Password change
- Profile
"""

from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Password management
    path('password/change/', views.password_change_view, name='password_change'),
    
    # Profile
    path('profile/', views.profile_view, name='profile'),
]
