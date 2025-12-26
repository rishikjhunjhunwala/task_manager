"""
Custom middleware for session management.

Implements:
- 30-minute idle timeout (resets on each request)
- 8-hour absolute session timeout (from login time)
- Session invalidation handling
"""

from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages


class SessionIdleTimeoutMiddleware:
    """
    Middleware to enforce session timeouts.
    
    Settings used:
    - SESSION_IDLE_TIMEOUT: Seconds of inactivity before logout (default: 1800 = 30 min)
    - SESSION_COOKIE_AGE: Absolute session timeout (default: 28800 = 8 hours)
    
    Session keys used:
    - last_activity: Timestamp of last request
    - session_start: Timestamp when session was created (set at login)
    """
    
    # URLs that don't require authentication or timeout checks
    EXEMPT_URLS = [
        '/login/',
        '/logout/',
        '/admin/login/',
        '/static/',
        '/media/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip for unauthenticated users or exempt URLs
        if not request.user.is_authenticated:
            return self.get_response(request)
        
        if self._is_exempt_url(request.path):
            return self.get_response(request)
        
        now = timezone.now()
        
        # Check absolute session timeout (8 hours from login)
        session_start = request.session.get('session_start')
        if session_start:
            session_start_dt = timezone.datetime.fromisoformat(session_start)
            session_age = (now - session_start_dt).total_seconds()
            absolute_timeout = getattr(settings, 'SESSION_COOKIE_AGE', 8 * 3600)
            
            if session_age > absolute_timeout:
                return self._handle_timeout(
                    request, 
                    'Your session has expired. Please log in again.'
                )
        
        # Check idle timeout (30 minutes since last activity)
        last_activity = request.session.get('last_activity')
        if last_activity:
            last_activity_dt = timezone.datetime.fromisoformat(last_activity)
            idle_time = (now - last_activity_dt).total_seconds()
            idle_timeout = getattr(settings, 'SESSION_IDLE_TIMEOUT', 30 * 60)
            
            if idle_time > idle_timeout:
                return self._handle_timeout(
                    request,
                    'You have been logged out due to inactivity.'
                )
        
        # Update last activity timestamp
        request.session['last_activity'] = now.isoformat()
        
        return self.get_response(request)
    
    def _is_exempt_url(self, path):
        """Check if the URL is exempt from timeout checks."""
        for exempt_url in self.EXEMPT_URLS:
            if path.startswith(exempt_url):
                return True
        return False
    
    def _handle_timeout(self, request, message):
        """Log out the user and redirect to login with message."""
        logout(request)
        messages.warning(request, message)
        
        # Store the original URL for redirect after login
        login_url = reverse('accounts:login')
        next_url = request.get_full_path()
        
        # Don't redirect back to logout or admin URLs
        if '/logout/' in next_url or '/admin/' in next_url:
            return redirect(login_url)
        
        return redirect(f'{login_url}?next={next_url}')


class PasswordChangeRequiredMiddleware:
    """
    Middleware to enforce password change for users with must_change_password=True.
    
    Redirects to password change page for any authenticated request
    except for the password change page itself and logout.
    """
    
    ALLOWED_URLS = [
        '/password/change/',
        '/logout/',
        '/static/',
        '/media/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)
        
        # Check if user must change password
        if hasattr(request.user, 'must_change_password') and request.user.must_change_password:
            # Allow access to certain URLs
            if not self._is_allowed_url(request.path):
                messages.warning(
                    request, 
                    'You must change your password before continuing.'
                )
                return redirect('accounts:password_change')
        
        return self.get_response(request)
    
    def _is_allowed_url(self, path):
        """Check if the URL is allowed during forced password change."""
        for allowed_url in self.ALLOWED_URLS:
            if path.startswith(allowed_url):
                return True
        return False


class PasswordExpiryMiddleware:
    """
    Middleware to check if user's password has expired (90 days).
    
    Redirects to password change page if password is expired.
    """
    
    ALLOWED_URLS = [
        '/password/change/',
        '/logout/',
        '/static/',
        '/media/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)
        
        # Check if password has expired
        if hasattr(request.user, 'is_password_expired') and request.user.is_password_expired():
            # Allow access to certain URLs
            if not self._is_allowed_url(request.path):
                messages.warning(
                    request, 
                    'Your password has expired. Please set a new password.'
                )
                return redirect('accounts:password_change')
        
        return self.get_response(request)
    
    def _is_allowed_url(self, path):
        """Check if the URL is allowed during password expiry."""
        for allowed_url in self.ALLOWED_URLS:
            if path.startswith(allowed_url):
                return True
        return False
