"""
Views for accounts app.

Phase 3: Authentication & Security views including:
- Custom login with lockout handling and domain validation
- Logout with session cleanup
- Password change (normal and forced first-login)
- Password expiry handling
"""

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from django.urls import reverse
from django.http import HttpResponseRedirect

from .forms import LoginForm, PasswordChangeForm, FirstLoginPasswordChangeForm
from .services import invalidate_user_sessions


@csrf_protect
@never_cache
@require_http_methods(['GET', 'POST'])
def login_view(request):
    """
    Custom login view with:
    - Email domain validation
    - Account lockout handling
    - Password expiry check
    - Session initialization
    """
    # Redirect if already authenticated
    if request.user.is_authenticated:
        return redirect('tasks:dashboard')
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        
        if form.is_valid():
            user = form.get_user()
            
            # Perform login
            login(request, user)
            
            # Initialize session timestamps
            now = timezone.now()
            request.session['session_start'] = now.isoformat()
            request.session['last_activity'] = now.isoformat()
            
            # Update last login
            user.last_login = now
            user.save(update_fields=['last_login'])
            
            # Check if password change is required
            if user.must_change_password:
                messages.info(request, 'Please set a new password to continue.')
                return redirect('accounts:password_change')
            
            # Check if password has expired
            if user.is_password_expired():
                messages.warning(request, 'Your password has expired. Please set a new password.')
                return redirect('accounts:password_change')
            
            # Success message
            messages.success(request, f'Welcome back, {user.get_short_name()}!')
            
            # Redirect to next URL or dashboard
            next_url = request.GET.get('next', request.POST.get('next', ''))
            if next_url and next_url != reverse('accounts:logout'):
                return HttpResponseRedirect(next_url)
            
            return redirect('tasks:dashboard')
    else:
        form = LoginForm(request)
    
    return render(request, 'accounts/login.html', {'form': form})


@require_http_methods(['GET', 'POST'])
def logout_view(request):
    """
    Logout view with session cleanup.
    """
    if request.user.is_authenticated:
        # Clear session data
        request.session.flush()
        
        # Perform logout
        logout(request)
        
        messages.success(request, 'You have been logged out successfully.')
    
    return redirect('accounts:login')


@login_required
@csrf_protect
@never_cache
@require_http_methods(['GET', 'POST'])
def password_change_view(request):
    """
    Password change view.
    
    Handles both:
    - Normal password change (requires current password)
    - First login password change (must_change_password=True)
    """
    user = request.user
    is_first_login = user.must_change_password
    is_expired = user.is_password_expired()
    
    # Choose appropriate form
    if is_first_login:
        FormClass = FirstLoginPasswordChangeForm
        template = 'accounts/password_change_first_login.html'
    else:
        FormClass = PasswordChangeForm
        template = 'accounts/password_change.html'
    
    if request.method == 'POST':
        form = FormClass(user, data=request.POST)
        
        if form.is_valid():
            # Save new password
            user = form.save()
            
            # Invalidate other sessions (security measure)
            invalidate_user_sessions(user, exclude_session_key=request.session.session_key)
            
            # Update session auth hash to prevent logout
            update_session_auth_hash(request, user)
            
            messages.success(request, 'Your password has been changed successfully!')
            
            return redirect('tasks:dashboard')
    else:
        form = FormClass(user)
    
    context = {
        'form': form,
        'is_first_login': is_first_login,
        'is_expired': is_expired,
    }
    
    return render(request, template, context)


@login_required
@require_http_methods(['GET'])
def profile_view(request):
    """
    User profile view.
    Shows user information and account settings.
    """
    user = request.user
    
    context = {
        'user': user,
        'password_expiry_days': None,
    }
    
    # Calculate days until password expires
    if user.password_changed_at:
        from django.conf import settings
        expiry_days = getattr(settings, 'PASSWORD_EXPIRY_DAYS', 90)
        expiry_date = user.password_changed_at + timezone.timedelta(days=expiry_days)
        days_remaining = (expiry_date - timezone.now()).days
        context['password_expiry_days'] = max(0, days_remaining)
    
    return render(request, 'accounts/profile.html', context)
