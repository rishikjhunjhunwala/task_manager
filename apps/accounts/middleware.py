"""
Custom middleware for accounts app.

Includes:
- Session idle timeout middleware (30 minutes)
- Password change required middleware (first login)
- Password expiry middleware (90 days)
"""

from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import logout


class SessionIdleTimeoutMiddleware:
    """
    Middleware to log out users after a period of inactivity.
    
    Default: 30 minutes (SESSION_IDLE_TIMEOUT setting)
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            last_activity = request.session.get('last_activity')
            
            if last_activity:
                # Calculate time since last activity
                from datetime import datetime
                last_activity_time = datetime.fromisoformat(last_activity)
                idle_timeout = getattr(settings, 'SESSION_IDLE_TIMEOUT', 30 * 60)  # 30 minutes default
                
                # Make last_activity_time timezone-aware if needed
                if timezone.is_naive(last_activity_time):
                    last_activity_time = timezone.make_aware(last_activity_time)
                
                time_since_activity = (timezone.now() - last_activity_time).total_seconds()
                
                if time_since_activity > idle_timeout:
                    # Session has timed out due to inactivity
                    logout(request)
                    from django.contrib import messages
                    messages.warning(request, 'Your session has expired due to inactivity. Please log in again.')
                    return redirect('accounts:login')
            
            # Update last activity timestamp
            request.session['last_activity'] = timezone.now().isoformat()
        
        response = self.get_response(request)
        return response


class PasswordChangeRequiredMiddleware:
    """
    Middleware to redirect users who must change their password (first login).
    
    Checks: user.must_change_password flag
    """
    
    # URLs that are allowed even when password change is required
    EXEMPT_URLS = [
        'accounts:password_change_first_login',
        'accounts:logout',
        'admin:index',
        'admin:login',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            # Check if user must change password
            if getattr(request.user, 'must_change_password', False):
                # Get current URL name
                try:
                    from django.urls import resolve
                    current_url = resolve(request.path_info).url_name
                    current_namespace = resolve(request.path_info).namespace
                    full_url_name = f"{current_namespace}:{current_url}" if current_namespace else current_url
                except:
                    full_url_name = None
                
                # Check if current URL is exempt
                if full_url_name not in self.EXEMPT_URLS and not request.path.startswith('/admin/'):
                    return redirect('accounts:password_change_first_login')
        
        response = self.get_response(request)
        return response


class PasswordExpiryMiddleware:
    """
    Middleware to redirect users with expired passwords.
    
    Default expiry: 90 days (PASSWORD_EXPIRY_DAYS setting)
    """
    
    # URLs that are allowed even when password is expired
    EXEMPT_URLS = [
        'accounts:password_change',
        'accounts:password_change_first_login',
        'accounts:logout',
        'accounts:login',
        'admin:index',
        'admin:login',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            # Skip if must_change_password is set (handled by other middleware)
            if getattr(request.user, 'must_change_password', False):
                response = self.get_response(request)
                return response
            
            # Check if password is expired
            if hasattr(request.user, 'is_password_expired') and request.user.is_password_expired():
                # Get current URL name
                try:
                    from django.urls import resolve
                    current_url = resolve(request.path_info).url_name
                    current_namespace = resolve(request.path_info).namespace
                    full_url_name = f"{current_namespace}:{current_url}" if current_namespace else current_url
                except:
                    full_url_name = None
                
                # Check if current URL is exempt
                if full_url_name not in self.EXEMPT_URLS and not request.path.startswith('/admin/'):
                    from django.contrib import messages
                    messages.warning(request, 'Your password has expired. Please change it now.')
                    return redirect('accounts:password_change')
        
        response = self.get_response(request)
        return response
