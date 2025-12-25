"""
Admin configuration for accounts app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom User admin with email authentication and role management.
    """
    
    # List display
    list_display = (
        'email', 'first_name', 'last_name', 'role', 
        'department', 'is_active', 'is_locked_display', 'created_at'
    )
    list_filter = ('role', 'department', 'is_active', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    
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
            'fields': ('last_login', 'created_at'),
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
    
    readonly_fields = ('created_at', 'last_login', 'password_changed_at')
    
    def is_locked_display(self, obj):
        """Display whether the account is locked."""
        return obj.is_locked()
    is_locked_display.boolean = True
    is_locked_display.short_description = 'Locked'

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('department')
