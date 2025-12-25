"""
Admin configuration for activity_log app.
"""

from django.contrib import admin
from .models import TaskActivity


@admin.register(TaskActivity)
class TaskActivityAdmin(admin.ModelAdmin):
    """Admin for TaskActivity model."""
    
    list_display = (
        'task', 'user', 'action_type', 'description_preview', 
        'field_name', 'created_at'
    )
    list_filter = ('action_type', 'created_at', 'user')
    search_fields = (
        'task__reference_number', 'description', 
        'user__email', 'user__first_name', 'user__last_name'
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    
    readonly_fields = (
        'task', 'user', 'action_type', 'description',
        'field_name', 'old_value', 'new_value', 'created_at'
    )

    def description_preview(self, obj):
        """Show truncated description."""
        return obj.description[:80] + '...' if len(obj.description) > 80 else obj.description
    description_preview.short_description = 'Description'

    def has_add_permission(self, request):
        """Prevent manual creation of activity logs."""
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent editing of activity logs."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of activity logs."""
        return False

    def get_queryset(self, request):
        """Optimize with select_related."""
        return super().get_queryset(request).select_related('task', 'user')
