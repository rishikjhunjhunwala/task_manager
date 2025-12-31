"""
Custom middleware for accounts app.

Includes:
- Session idle timeout middleware (30 minutes)
- Password change required middleware (first login)
- Password expiry middleware (90 days)

All middlewares properly handle HTMX/AJAX requests to prevent redirect loops.
"""

from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpResponse


def is_ajax_or_htmx_request(request):
    """
    Check if the request is an AJAX or HTMX request.
    
    Returns True for:
    - HTMX requests (HX-Request header)
    - XMLHttpRequest (X-Requested-With header)
    - Fetch API requests that set Accept: application/json
    """
    # HTMX request
    if request.headers.get('HX-Request') == 'true':
        return True
    
    # Traditional AJAX (XMLHttpRequest)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return True
    
    # Fetch API with JSON accept header (but not browser navigation)
    accept = request.headers.get('Accept', '')
    if 'application/json' in accept and 'text/html' not in accept:
        return True
    
    return False


def get_auth_redirect_response(request, redirect_url):
    """
    Return appropriate response for auth redirects based on request type.
    
    - For HTMX requests: Return 204 No Content (silent fail) for background requests,
      or HX-Redirect header for user-initiated requests
    - For AJAX requests: Return 401 with JSON
    - For normal requests: Return standard redirect
    """
    if request.headers.get('HX-Request') == 'true':
        # Check if this is a background/polling request vs user-initiated
        # Background requests: badge counts, polling, auto-refresh
        # User-initiated: form submissions, button clicks
        
        is_background = _is_background_htmx_request(request)
        
        if is_background:
            # Silent fail - don't disrupt the UI
            return HttpResponse(status=204)
        else:
            # User action - redirect the full page
            response = HttpResponse(status=200)
            response['HX-Redirect'] = redirect_url
            return response
    
    elif request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Traditional AJAX - return 401 Unauthorized
        return HttpResponse(
            '{"error": "Authentication required", "redirect": "' + redirect_url + '"}',
            content_type='application/json',
            status=401
        )
    
    else:
        # Normal browser request - standard redirect
        return redirect(redirect_url)


def _is_background_htmx_request(request):
    """
    Determine if an HTMX request is a background request (polling, auto-refresh)
    vs a user-initiated request (click, form submit).
    
    Background requests should fail silently.
    User-initiated requests should redirect the full page.
    """
    # GET requests are typically polling/refresh
    if request.method == 'GET':
        # Check URL patterns that indicate background requests
        background_patterns = [
            'badge', 'count', 'poll', 'refresh', 'check', 'status',
            'notification', 'alert', 'update', 'sidebar', 'history',
            '__debug__',  # Django Debug Toolbar
        ]
        path_lower = request.path.lower()
        if any(pattern in path_lower for pattern in background_patterns):
            return True
        
        # Check HX-Trigger for polling indicators
        trigger = request.headers.get('HX-Trigger', '').lower()
        if any(t in trigger for t in ['load', 'every', 'poll', 'revealed']):
            return True
    
    # POST/PUT/DELETE are typically user-initiated
    # But check for specific background POST patterns
    if request.method == 'POST':
        background_post_patterns = ['heartbeat', 'ping', 'track', 'log']
        path_lower = request.path.lower()
        if any(pattern in path_lower for pattern in background_post_patterns):
            return True
    
    return False


class SessionIdleTimeoutMiddleware:
    """
    Middleware to log out users after a period of inactivity.
    
    Default: 30 minutes (SESSION_IDLE_TIMEOUT setting)
    
    For HTMX/AJAX requests, returns appropriate response instead of redirect.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            last_activity = request.session.get('last_activity')
            
            if last_activity:
                from datetime import datetime
                last_activity_time = datetime.fromisoformat(last_activity)
                idle_timeout = getattr(settings, 'SESSION_IDLE_TIMEOUT', 30 * 60)
                
                if timezone.is_naive(last_activity_time):
                    last_activity_time = timezone.make_aware(last_activity_time)
                
                time_since_activity = (timezone.now() - last_activity_time).total_seconds()
                
                if time_since_activity > idle_timeout:
                    logout(request)
                    
                    # Don't add message for AJAX/HTMX requests
                    if not is_ajax_or_htmx_request(request):
                        from django.contrib import messages
                        messages.warning(
                            request, 
                            'Your session has expired due to inactivity. Please log in again.'
                        )
                    
                    login_url = reverse('accounts:login')
                    return get_auth_redirect_response(request, login_url)
            
            # Update last activity timestamp (skip for background requests)
            if not _is_background_htmx_request(request):
                request.session['last_activity'] = timezone.now().isoformat()
        
        response = self.get_response(request)
        return response


class PasswordChangeRequiredMiddleware:
    """
    Middleware to redirect users who must change their password (first login).
    
    Checks: user.must_change_password flag
    
    For HTMX/AJAX requests, returns appropriate response instead of redirect.
    """
    
    # URLs that are allowed even when password change is required
    EXEMPT_URLS = [
        'accounts:password_change_first_login',
        'accounts:logout',
        'admin:index',
        'admin:login',
    ]
    
    # URL path prefixes that are always exempt
    EXEMPT_PATH_PREFIXES = [
        '/admin/',
        '/static/',
        '/media/',
        '/__debug__/',  # Django Debug Toolbar
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            if getattr(request.user, 'must_change_password', False):
                # Check path prefixes first (fast check)
                if any(request.path.startswith(prefix) for prefix in self.EXEMPT_PATH_PREFIXES):
                    return self.get_response(request)
                
                # Check URL names
                try:
                    from django.urls import resolve
                    resolved = resolve(request.path_info)
                    current_url = resolved.url_name
                    current_namespace = resolved.namespace
                    full_url_name = f"{current_namespace}:{current_url}" if current_namespace else current_url
                except:
                    full_url_name = None
                
                if full_url_name not in self.EXEMPT_URLS:
                    redirect_url = reverse('accounts:password_change_first_login')
                    return get_auth_redirect_response(request, redirect_url)
        
        response = self.get_response(request)
        return response


class PasswordExpiryMiddleware:
    """
    Middleware to redirect users with expired passwords.
    
    Default expiry: 90 days (PASSWORD_EXPIRY_DAYS setting)
    
    For HTMX/AJAX requests, returns appropriate response instead of redirect.
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
    
    # URL path prefixes that are always exempt
    EXEMPT_PATH_PREFIXES = [
        '/admin/',
        '/static/',
        '/media/',
        '/__debug__/',  # Django Debug Toolbar
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            # Skip if must_change_password is set (handled by other middleware)
            if getattr(request.user, 'must_change_password', False):
                return self.get_response(request)
            
            # Check if password is expired
            if hasattr(request.user, 'is_password_expired') and request.user.is_password_expired():
                # Check path prefixes first (fast check)
                if any(request.path.startswith(prefix) for prefix in self.EXEMPT_PATH_PREFIXES):
                    return self.get_response(request)
                
                # Check URL names
                try:
                    from django.urls import resolve
                    resolved = resolve(request.path_info)
                    current_url = resolved.url_name
                    current_namespace = resolved.namespace
                    full_url_name = f"{current_namespace}:{current_url}" if current_namespace else current_url
                except:
                    full_url_name = None
                
                if full_url_name not in self.EXEMPT_URLS:
                    # Don't add message for AJAX/HTMX requests
                    if not is_ajax_or_htmx_request(request):
                        from django.contrib import messages
                        messages.warning(request, 'Your password has expired. Please change it now.')
                    
                    redirect_url = reverse('accounts:password_change')
                    return get_auth_redirect_response(request, redirect_url)
        
        response = self.get_response(request)
        return response