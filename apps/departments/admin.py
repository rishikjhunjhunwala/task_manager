"""
Admin configuration for departments app.
"""

from django.contrib import admin
from .models import Department


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """Admin for Department model."""
    
    list_display = ('name', 'code', 'head', 'employee_count', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'code')
    ordering = ('name',)
    
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'head')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        """Optimize with select_related."""
        return super().get_queryset(request).select_related('head')
