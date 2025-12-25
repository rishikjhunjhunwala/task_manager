"""
Admin configuration for tasks app.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Task, Comment, Attachment


class CommentInline(admin.TabularInline):
    """Inline admin for comments on task detail."""
    model = Comment
    extra = 0
    readonly_fields = ('author', 'content', 'created_at')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


class AttachmentInline(admin.StackedInline):
    """Inline admin for attachment on task detail."""
    model = Attachment
    extra = 0
    readonly_fields = ('uploaded_by', 'filename', 'file_size', 'uploaded_at')
    can_delete = True
    max_num = 1


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """Admin for Task model."""
    
    list_display = (
        'reference_number', 'title', 'assignee', 'created_by',
        'status_display', 'priority_display', 'deadline', 'task_type',
        'is_overdue_display', 'created_at'
    )
    list_filter = (
        'status', 'priority', 'task_type', 'department',
        'created_at', 'deadline'
    )
    search_fields = ('reference_number', 'title', 'description')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    
    readonly_fields = (
        'reference_number', 'task_type', 'created_at', 'updated_at',
        'completed_at', 'cancelled_at', 'escalated_to_sm2_at', 
        'escalated_to_sm1_at'
    )
    
    fieldsets = (
        (None, {
            'fields': ('reference_number', 'title', 'description')
        }),
        ('Assignment', {
            'fields': ('assignee', 'created_by', 'department', 'task_type')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority', 'deadline')
        }),
        ('Tracking', {
            'fields': (
                'deadline_reminder_sent', 'first_overdue_email_sent',
                'escalated_to_sm2_at', 'escalated_to_sm1_at'
            ),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at', 'cancelled_at'),
            'classes': ('collapse',),
        }),
        ('Source', {
            'fields': ('source', 'source_reference'),
            'classes': ('collapse',),
        }),
    )
    
    inlines = [AttachmentInline, CommentInline]

    def get_queryset(self, request):
        """Optimize with select_related."""
        return super().get_queryset(request).select_related(
            'assignee', 'created_by', 'department', 'cancelled_by'
        )

    def status_display(self, obj):
        """Display status with color coding."""
        colors = {
            'pending': '#FFA500',      # Orange
            'in_progress': '#3498db',  # Blue
            'completed': '#27ae60',    # Green
            'verified': '#2ecc71',     # Bright green
            'cancelled': '#95a5a6',    # Gray
        }
        color = colors.get(obj.status, '#000')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'

    def priority_display(self, obj):
        """Display priority with color coding."""
        colors = {
            'low': '#95a5a6',
            'medium': '#3498db',
            'high': '#e67e22',
            'critical': '#e74c3c',
        }
        color = colors.get(obj.priority, '#000')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_priority_display()
        )
    priority_display.short_description = 'Priority'
    priority_display.admin_order_field = 'priority'

    def is_overdue_display(self, obj):
        """Display overdue status."""
        if obj.is_overdue:
            return format_html('<span style="color: red;">⚠️ OVERDUE</span>')
        return ''
    is_overdue_display.short_description = 'Overdue'


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """Admin for Comment model."""
    
    list_display = ('task', 'author', 'content_preview', 'created_at')
    list_filter = ('created_at', 'author')
    search_fields = ('content', 'task__reference_number')
    ordering = ('-created_at',)
    
    readonly_fields = ('task', 'author', 'created_at')

    def content_preview(self, obj):
        """Show truncated content."""
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    """Admin for Attachment model."""
    
    list_display = ('task', 'filename', 'file_size_display', 'uploaded_by', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('filename', 'task__reference_number')
    ordering = ('-uploaded_at',)
    
    readonly_fields = ('filename', 'file_size', 'uploaded_at')

    def file_size_display(self, obj):
        """Show human-readable file size."""
        return obj.file_size_display
    file_size_display.short_description = 'Size'
