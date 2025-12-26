"""
Admin configuration for accounts app.
Enhanced with role/department filters and improved UX.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom User admin with email authentication and role management.
    Enhanced with visual indicators and quick actions.
    """
    
    # List display
    list_display = (
        'email', 'full_name_display', 'role_display', 
        'department', 'is_active_display', 'is_locked_display', 
        'password_status', 'created_at'
    )
    list_filter = ('role', 'department', 'is_active', 'is_staff', 'must_change_password')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('first_name', 'last_name')
    list_per_page = 25
    
    # Fieldsets for edit view
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal Info'), {'fields': ('first_name', 'last_name')}),
        (_('Organization'), {'fields': ('role', 'department')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',),
        }),
        (_('Security'), {
            'fields': (
                'must_change_password', 'failed_login_attempts', 
                'locked_until', 'password_changed_at'
            ),
        }),
        (_('Important dates'), {
            'fields': ('last_login', 'created_at', 'updated_at'),
        }),
    )
    
    # Fieldsets for add view
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'first_name', 'last_name', 
                'password1', 'password2', 'role', 'department'
            ),
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at', 'last_login', 'password_changed_at')
    
    actions = ['unlock_accounts', 'reset_passwords', 'deactivate_users', 'activate_users']
    
    # Custom display methods
    def full_name_display(self, obj):
        """Display full name."""
        return obj.get_full_name() or '-'
    full_name_display.short_description = 'Name'
    full_name_display.admin_order_field = 'first_name'
    
    def role_display(self, obj):
        """Display role with color coding."""
        colors = {
            'admin': '#7C3AED',        # Purple
            'senior_manager_1': '#DC2626',  # Red
            'senior_manager_2': '#EA580C',  # Orange
            'manager': '#2563EB',      # Blue
            'employee': '#059669',     # Green
        }
        color = colors.get(obj.role, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px; font-weight: 500;">{}</span>',
            color, obj.get_role_display()
        )
    role_display.short_description = 'Role'
    role_display.admin_order_field = 'role'
    
    def is_active_display(self, obj):
        """Display active status with icon."""
        if obj.is_active:
            return format_html('<span style="color: #059669;">●</span> Active')
        return format_html('<span style="color: #DC2626;">●</span> Inactive')
    is_active_display.short_description = 'Status'
    is_active_display.admin_order_field = 'is_active'
    
    def is_locked_display(self, obj):
        """Display whether the account is locked."""
        if obj.is_locked():
            return format_html('<span style="color: #DC2626;">🔒 Locked</span>')
        return format_html('<span style="color: #059669;">🔓</span>')
    is_locked_display.short_description = 'Lock'
    
    def password_status(self, obj):
        """Display password status."""
        if obj.must_change_password:
            return format_html('<span style="color: #F59E0B;">⚠️ Temp</span>')
        if obj.is_password_expired():
            return format_html('<span style="color: #DC2626;">⏰ Expired</span>')
        return format_html('<span style="color: #059669;">✓</span>')
    password_status.short_description = 'Password'

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('department')
    
    # Admin actions
    def unlock_accounts(self, request, queryset):
        """Unlock selected accounts."""
        count = 0
        for user in queryset:
            if user.is_locked():
                user.unlock_account()
                count += 1
        self.message_user(request, f'{count} account(s) unlocked.')
    unlock_accounts.short_description = 'Unlock selected accounts'
    
    def reset_passwords(self, request, queryset):
        """Reset passwords for selected users."""
        from .services import reset_user_password
        count = 0
        for user in queryset:
            reset_user_password(user)
            count += 1
        self.message_user(request, f'Password reset for {count} user(s). Emails sent.')
    reset_passwords.short_description = 'Reset passwords and send email'
    
    def deactivate_users(self, request, queryset):
        """Deactivate selected users."""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} user(s) deactivated.')
    deactivate_users.short_description = 'Deactivate selected users'
    
    def activate_users(self, request, queryset):
        """Activate selected users."""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} user(s) activated.')
    activate_users.short_description = 'Activate selected users'
