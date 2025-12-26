"""
Views for accounts app.

Includes:
- Authentication views (login, logout, password change)
- User management views (admin only)
- Profile view
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse

from apps.departments.models import Department
from .forms import (
    LoginForm, PasswordChangeForm, FirstLoginPasswordChangeForm,
    AdminUserCreationForm, AdminUserEditForm
)
from .services import (
    generate_temp_password, send_welcome_email, reset_user_password,
    unlock_user_account, deactivate_user, get_user_task_summary,
    invalidate_user_sessions
)

User = get_user_model()


# =============================================================================
# Permission Decorators
# =============================================================================

def admin_required(view_func):
    """Decorator to require admin role."""
    def check_admin(user):
        return user.is_authenticated and user.role == 'admin'
    
    decorated_view = user_passes_test(check_admin, login_url='accounts:login')(view_func)
    return decorated_view


# =============================================================================
# Authentication Views
# =============================================================================

def login_view(request):
    """
    Custom login view with email authentication.
    Handles domain validation, lockout, and password expiry.
    """
    if request.user.is_authenticated:
        return redirect('tasks:dashboard')
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            
            # Try to get user first to check lockout
            try:
                user = User.objects.get(email__iexact=email)
                if user.is_locked():
                    remaining = (user.locked_until - timezone.now()).seconds // 60
                    messages.error(
                        request, 
                        f'Account is locked. Please try again in {remaining + 1} minutes.'
                    )
                    return render(request, 'accounts/login.html', {'form': form})
            except User.DoesNotExist:
                pass
            
            # Authenticate
            user = authenticate(request, username=email, password=password)
            
            if user is not None:
                if not user.is_active:
                    messages.error(request, 'Your account has been deactivated. Please contact admin.')
                    return render(request, 'accounts/login.html', {'form': form})
                
                login(request, user)
                
                # Check if password change required
                if user.must_change_password:
                    messages.info(request, 'Please change your temporary password.')
                    return redirect('accounts:password_change_first_login')
                
                # Check password expiry
                if user.is_password_expired():
                    messages.warning(request, 'Your password has expired. Please change it now.')
                    return redirect('accounts:password_change')
                
                messages.success(request, f'Welcome back, {user.get_short_name()}!')
                
                # Redirect to next URL or dashboard
                next_url = request.GET.get('next', 'tasks:dashboard')
                return redirect(next_url)
            else:
                messages.error(request, 'Invalid email or password.')
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})


@login_required
def logout_view(request):
    """Log out the user and redirect to login page."""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('accounts:login')


@login_required
def password_change_view(request):
    """
    Regular password change view.
    Requires current password.
    """
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = request.user
            new_password = form.cleaned_data['new_password']
            
            # Add current password to history before changing
            user.add_password_to_history(user.password)
            
            # Set new password
            user.set_password(new_password)
            user.password_changed_at = timezone.now()
            user.must_change_password = False
            user.save()
            
            # Invalidate other sessions
            invalidate_user_sessions(user)
            
            # Re-login with new password (specify backend due to multiple backends)
            login(request, user, backend='apps.accounts.backends.EmailAuthBackend')
            
            messages.success(request, 'Password changed successfully.')
            return redirect('tasks:dashboard')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'accounts/password_change.html', {
        'form': form,
        'is_first_login': False,
    })


@login_required
def password_change_first_login_view(request):
    """
    First login password change view.
    Does not require current password.
    """
    if not request.user.must_change_password:
        return redirect('tasks:dashboard')
    
    if request.method == 'POST':
        form = FirstLoginPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = request.user
            new_password = form.cleaned_data['new_password']
            
            # Set new password
            user.set_password(new_password)
            user.password_changed_at = timezone.now()
            user.must_change_password = False
            user.save()
            
            # Re-login with new password (specify backend due to multiple backends)
            login(request, user, backend='apps.accounts.backends.EmailAuthBackend')
            
            messages.success(request, 'Password set successfully. Welcome to Task Manager!')
            return redirect('tasks:dashboard')
    else:
        form = FirstLoginPasswordChangeForm(request.user)
    
    return render(request, 'accounts/password_change_first_login.html', {
        'form': form,
        'is_first_login': True,
    })


@login_required
def profile_view(request):
    """Display user profile."""
    user = request.user
    
    # Calculate password expiry
    days_until_expiry = None
    if user.password_changed_at:
        expiry_days = getattr(settings, 'PASSWORD_EXPIRY_DAYS', 90)
        expiry_date = user.password_changed_at + timezone.timedelta(days=expiry_days)
        days_until_expiry = (expiry_date - timezone.now()).days
    
    context = {
        'user': user,
        'days_until_expiry': days_until_expiry,
    }
    return render(request, 'accounts/profile.html', context)


# =============================================================================
# User Management Views (Admin Only)
# =============================================================================

@login_required
@admin_required
def user_list_view(request):
    """
    List all users with filters.
    Admin only.
    """
    users = User.objects.select_related('department').order_by('first_name', 'last_name')
    
    # Search
    search = request.GET.get('search', '').strip()
    if search:
        users = users.filter(
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    
    # Filter by role
    role = request.GET.get('role', '')
    if role:
        users = users.filter(role=role)
    
    # Filter by department
    department = request.GET.get('department', '')
    if department:
        users = users.filter(department_id=department)
    
    # Filter by status
    status = request.GET.get('status', '')
    if status == 'active':
        users = users.filter(is_active=True)
    elif status == 'inactive':
        users = users.filter(is_active=False)
    elif status == 'locked':
        users = users.filter(locked_until__gt=timezone.now())
    elif status == 'password_change':
        users = users.filter(must_change_password=True)
    
    # Pagination
    paginator = Paginator(users, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    departments = Department.objects.all().order_by('name')
    roles = User.Role.choices
    
    context = {
        'page_obj': page_obj,
        'users': page_obj,
        'departments': departments,
        'roles': roles,
        'search': search,
        'selected_role': role,
        'selected_department': department,
        'selected_status': status,
        'total_count': paginator.count,
    }
    return render(request, 'accounts/user_list.html', context)


@login_required
@admin_required
def user_create_view(request):
    """
    Create a new user.
    Admin only.
    """
    if request.method == 'POST':
        form = AdminUserCreationForm(request.POST)
        if form.is_valid():
            # Generate temporary password
            temp_password = generate_temp_password()
            
            # Create user with temporary password
            # We use create_user to properly hash the password
            user = User.objects.create_user(
                email=form.cleaned_data['email'],
                password=temp_password,
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                role=form.cleaned_data['role'],
                department=form.cleaned_data.get('department'),
                must_change_password=True,
            )
            
            # Send welcome email
            email_sent = send_welcome_email(user, temp_password)
            
            if email_sent:
                messages.success(
                    request, 
                    f'User {user.get_full_name()} created successfully. '
                    f'Welcome email sent to {user.email}.'
                )
            else:
                messages.warning(
                    request,
                    f'User {user.get_full_name()} created successfully. '
                    f'However, failed to send welcome email. '
                    f'Temporary password: {temp_password}'
                )
            
            return redirect('accounts:user_list')
    else:
        form = AdminUserCreationForm()
    
    return render(request, 'accounts/user_form.html', {
        'form': form,
        'is_edit': False,
        'title': 'Create User',
    })


@login_required
@admin_required
def user_edit_view(request, pk):
    """
    Edit an existing user.
    Admin only.
    """
    user = get_object_or_404(User, pk=pk)
    
    # Prevent editing yourself through this view
    if user == request.user:
        messages.warning(request, 'Please use the profile page to edit your own account.')
        return redirect('accounts:profile')
    
    # Get task summary for deactivation warning
    task_summary = get_user_task_summary(user)
    
    if request.method == 'POST':
        form = AdminUserEditForm(request.POST, instance=user)
        if form.is_valid():
            old_is_active = user.is_active
            user = form.save()
            
            # If user was deactivated, invalidate sessions
            if old_is_active and not user.is_active:
                invalidate_user_sessions(user)
                messages.warning(
                    request,
                    f'User {user.get_full_name()} has been deactivated. '
                    f'All active sessions have been terminated.'
                )
            else:
                messages.success(request, f'User {user.get_full_name()} updated successfully.')
            
            return redirect('accounts:user_list')
    else:
        form = AdminUserEditForm(instance=user)
    
    return render(request, 'accounts/user_form.html', {
        'form': form,
        'is_edit': True,
        'edit_user': user,
        'title': f'Edit User: {user.get_full_name()}',
        'task_summary': task_summary,
    })


@login_required
@admin_required
@require_POST
def user_reset_password_view(request, pk):
    """
    Reset user's password and send email.
    Admin only. POST request only.
    """
    user = get_object_or_404(User, pk=pk)
    
    temp_password, email_sent = reset_user_password(user)
    
    if email_sent:
        messages.success(
            request,
            f'Password reset for {user.get_full_name()}. '
            f'New credentials sent to {user.email}.'
        )
    else:
        messages.warning(
            request,
            f'Password reset for {user.get_full_name()}. '
            f'Failed to send email. Temporary password: {temp_password}'
        )
    
    return redirect('accounts:user_edit', pk=pk)


@login_required
@admin_required
@require_POST
def user_unlock_view(request, pk):
    """
    Unlock a user's account.
    Admin only. POST request only.
    """
    user = get_object_or_404(User, pk=pk)
    
    if unlock_user_account(user):
        messages.success(request, f'Account for {user.get_full_name()} has been unlocked.')
    else:
        messages.info(request, f'Account for {user.get_full_name()} was not locked.')
    
    return redirect('accounts:user_edit', pk=pk)


@login_required
@admin_required
@require_POST
def user_deactivate_view(request, pk):
    """
    Deactivate a user's account.
    Admin only. POST request only.
    """
    user = get_object_or_404(User, pk=pk)
    
    if user == request.user:
        messages.error(request, 'You cannot deactivate your own account.')
        return redirect('accounts:user_list')
    
    sessions_invalidated = deactivate_user(user)
    
    messages.warning(
        request,
        f'User {user.get_full_name()} has been deactivated. '
        f'{sessions_invalidated} active session(s) terminated.'
    )
    
    return redirect('accounts:user_list')


@login_required
@admin_required
@require_POST
def user_activate_view(request, pk):
    """
    Activate a user's account.
    Admin only. POST request only.
    """
    user = get_object_or_404(User, pk=pk)
    
    user.is_active = True
    user.save(update_fields=['is_active'])
    
    messages.success(request, f'User {user.get_full_name()} has been activated.')
    
    return redirect('accounts:user_list')


# =============================================================================
# API/HTMX Views
# =============================================================================

@login_required
@admin_required
def user_task_warning_view(request, pk):
    """
    HTMX endpoint to get task warning for user deactivation.
    Returns HTML partial.
    """
    user = get_object_or_404(User, pk=pk)
    task_summary = get_user_task_summary(user)
    
    return render(request, 'accounts/partials/task_warning.html', {
        'user': user,
        'task_summary': task_summary,
    })


# Import settings for profile view
from django.conf import settings