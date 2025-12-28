"""
Task filters using django-filter.

Provides filtering capabilities for task list views:
- Status filter (multi-select)
- Priority filter (multi-select)
- Deadline filter (today, this week, overdue, custom range)
- Department filter (Manager+ only)
- Assignee filter (Manager+ only)
- Search (title, description, reference_number)
"""

import django_filters
from django import forms
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from .models import Task
from apps.departments.models import Department
from apps.accounts.models import User


class TaskFilter(django_filters.FilterSet):
    """
    Comprehensive task filter for list views.
    
    Usage in views:
        filterset = TaskFilter(request.GET, queryset=queryset, request=request)
        tasks = filterset.qs
    """
    
    # Search across multiple fields
    search = django_filters.CharFilter(
        method='filter_search',
        label='Search',
        widget=forms.TextInput(attrs={
            'placeholder': 'Search tasks...',
            'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            'hx-get': '',  # Will be set in template
            'hx-trigger': 'keyup changed delay:300ms',
            'hx-target': '#task-list-container',
            'hx-push-url': 'true',
            'hx-include': '[name]',
        })
    )
    
    # Status filter - multi-select
    status = django_filters.MultipleChoiceFilter(
        choices=Task.Status.choices,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500',
        }),
        label='Status'
    )
    
    # Priority filter - multi-select
    priority = django_filters.MultipleChoiceFilter(
        choices=Task.Priority.choices,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500',
        }),
        label='Priority'
    )
    
    # Deadline filter - predefined choices + custom range
    deadline_filter = django_filters.ChoiceFilter(
        method='filter_deadline',
        choices=[
            ('', 'All Deadlines'),
            ('today', 'Due Today'),
            ('tomorrow', 'Due Tomorrow'),
            ('this_week', 'Due This Week'),
            ('next_week', 'Due Next Week'),
            ('overdue', 'Overdue'),
            ('no_deadline', 'No Deadline'),
            ('custom', 'Custom Range'),
        ],
        label='Deadline',
        empty_label=None,
        widget=forms.Select(attrs={
            'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            'hx-get': '',
            'hx-trigger': 'change',
            'hx-target': '#task-list-container',
            'hx-push-url': 'true',
            'hx-include': '[name]',
        })
    )
    
    # Custom date range filters (shown when deadline_filter == 'custom')
    deadline_from = django_filters.DateFilter(
        field_name='deadline',
        lookup_expr='gte',
        label='From Date',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        })
    )
    
    deadline_to = django_filters.DateFilter(
        field_name='deadline',
        lookup_expr='lte',
        label='To Date',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        })
    )
    
    # Department filter (Manager+ only) - populated dynamically
    department = django_filters.ModelChoiceFilter(
        queryset=Department.objects.all(),
        label='Department',
        empty_label='All Departments',
        widget=forms.Select(attrs={
            'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            'hx-get': '',
            'hx-trigger': 'change',
            'hx-target': '#task-list-container',
            'hx-push-url': 'true',
            'hx-include': '[name]',
        })
    )
    
    # Assignee filter (Manager+ only) - populated dynamically
    assignee = django_filters.ModelChoiceFilter(
        queryset=User.objects.filter(is_active=True),
        label='Assignee',
        empty_label='All Assignees',
        widget=forms.Select(attrs={
            'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            'hx-get': '',
            'hx-trigger': 'change',
            'hx-target': '#task-list-container',
            'hx-push-url': 'true',
            'hx-include': '[name]',
        })
    )
    
    # Task type filter
    task_type = django_filters.ChoiceFilter(
        choices=[('', 'All Types')] + list(Task.TaskType.choices),
        label='Task Type',
        empty_label=None,
        widget=forms.Select(attrs={
            'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            'hx-get': '',
            'hx-trigger': 'change',
            'hx-target': '#task-list-container',
            'hx-push-url': 'true',
            'hx-include': '[name]',
        })
    )
    
    # Created by filter (for "I Assigned" view filtering)
    created_by = django_filters.ModelChoiceFilter(
        queryset=User.objects.filter(is_active=True),
        label='Created By',
        empty_label='All Creators',
        widget=forms.Select(attrs={
            'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        })
    )

    class Meta:
        model = Task
        fields = ['status', 'priority', 'department', 'assignee', 'task_type']

    def __init__(self, data=None, queryset=None, *, request=None, **kwargs):
        """
        Initialize filter with request context for role-based filtering.
        """
        super().__init__(data, queryset, request=request, **kwargs)
        self.request = request
        
        # Customize querysets based on user role
        if request and request.user.is_authenticated:
            user = request.user
            
            # Department filter - only show departments user can see
            if user.role in ['admin', 'senior_manager_1', 'senior_manager_2']:
                # Can see all departments
                self.filters['department'].queryset = Department.objects.all().order_by('name')
            elif user.role == 'manager':
                # Can only filter own department
                self.filters['department'].queryset = Department.objects.filter(
                    pk=user.department_id
                ) if user.department else Department.objects.none()
            else:
                # Employees don't get department filter
                self.filters['department'].queryset = Department.objects.none()
            
            # Assignee filter - based on role
            if user.role in ['admin', 'senior_manager_1', 'senior_manager_2']:
                # Can see all active users
                self.filters['assignee'].queryset = User.objects.filter(
                    is_active=True
                ).order_by('first_name', 'last_name')
            elif user.role == 'manager' and user.department:
                # Can only filter users in own department
                self.filters['assignee'].queryset = User.objects.filter(
                    is_active=True,
                    department=user.department
                ).order_by('first_name', 'last_name')
            else:
                # Employees don't get assignee filter
                self.filters['assignee'].queryset = User.objects.none()

    def filter_search(self, queryset, name, value):
        """
        Search across title, description, and reference_number.
        Case-insensitive partial matching.
        """
        if not value:
            return queryset
        
        return queryset.filter(
            Q(title__icontains=value) |
            Q(description__icontains=value) |
            Q(reference_number__icontains=value)
        )

    def filter_deadline(self, queryset, name, value):
        """
        Filter by deadline using predefined time ranges.
        """
        if not value:
            return queryset
        
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        if value == 'today':
            return queryset.filter(
                deadline__gte=today_start,
                deadline__lt=today_end
            )
        
        elif value == 'tomorrow':
            tomorrow_start = today_end
            tomorrow_end = tomorrow_start + timedelta(days=1)
            return queryset.filter(
                deadline__gte=tomorrow_start,
                deadline__lt=tomorrow_end
            )
        
        elif value == 'this_week':
            # Get start of week (Monday)
            days_since_monday = now.weekday()
            week_start = today_start - timedelta(days=days_since_monday)
            week_end = week_start + timedelta(days=7)
            return queryset.filter(
                deadline__gte=week_start,
                deadline__lt=week_end
            )
        
        elif value == 'next_week':
            days_since_monday = now.weekday()
            next_week_start = today_start - timedelta(days=days_since_monday) + timedelta(days=7)
            next_week_end = next_week_start + timedelta(days=7)
            return queryset.filter(
                deadline__gte=next_week_start,
                deadline__lt=next_week_end
            )
        
        elif value == 'overdue':
            return queryset.filter(
                deadline__lt=now,
                status__in=['pending', 'in_progress']
            )
        
        elif value == 'no_deadline':
            return queryset.filter(deadline__isnull=True)
        
        elif value == 'custom':
            # Custom range is handled by deadline_from and deadline_to filters
            return queryset
        
        return queryset


class DashboardTaskFilter(django_filters.FilterSet):
    """
    Simplified filter for dashboard views (My Tasks, Assigned to Me, etc.)
    """
    
    search = django_filters.CharFilter(
        method='filter_search',
        label='Search',
        widget=forms.TextInput(attrs={
            'placeholder': 'Search tasks...',
            'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        })
    )
    
    status = django_filters.MultipleChoiceFilter(
        choices=Task.Status.choices,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500',
        }),
        label='Status'
    )
    
    priority = django_filters.MultipleChoiceFilter(
        choices=Task.Priority.choices,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500',
        }),
        label='Priority'
    )

    class Meta:
        model = Task
        fields = ['status', 'priority']

    def filter_search(self, queryset, name, value):
        """Search across title, description, and reference_number."""
        if not value:
            return queryset
        
        return queryset.filter(
            Q(title__icontains=value) |
            Q(description__icontains=value) |
            Q(reference_number__icontains=value)
        )


# =============================================================================
# Helper Functions
# =============================================================================

def get_sorting_options():
    """
    Return available sorting options for task list.
    """
    return [
        ('deadline', 'Deadline (Earliest First)'),
        ('-deadline', 'Deadline (Latest First)'),
        ('-created_at', 'Created (Newest First)'),
        ('created_at', 'Created (Oldest First)'),
        ('-priority_order', 'Priority (Highest First)'),
        ('priority_order', 'Priority (Lowest First)'),
        ('status', 'Status (A-Z)'),
        ('-status', 'Status (Z-A)'),
        ('title', 'Title (A-Z)'),
        ('-title', 'Title (Z-A)'),
    ]


def apply_sorting(queryset, sort_param):
    """
    Apply sorting to queryset based on sort parameter.
    
    Args:
        queryset: Task queryset
        sort_param: Sort field (with optional '-' prefix for descending)
    
    Returns:
        Sorted queryset
    """
    from django.db.models import Case, When, Value, IntegerField
    
    # Default sorting
    if not sort_param:
        sort_param = '-created_at'
    
    # Handle priority sorting specially (convert to numeric order)
    if sort_param in ['priority_order', '-priority_order']:
        # Define priority order: critical=1, high=2, medium=3, low=4
        priority_order = Case(
            When(priority='critical', then=Value(1)),
            When(priority='high', then=Value(2)),
            When(priority='medium', then=Value(3)),
            When(priority='low', then=Value(4)),
            default=Value(5),
            output_field=IntegerField()
        )
        queryset = queryset.annotate(priority_order=priority_order)
        
        if sort_param.startswith('-'):
            return queryset.order_by('-priority_order', '-created_at')
        return queryset.order_by('priority_order', '-created_at')
    
    # Handle deadline sorting (nulls last)
    if sort_param == 'deadline':
        return queryset.order_by(
            models.F('deadline').asc(nulls_last=True),
            '-created_at'
        )
    elif sort_param == '-deadline':
        return queryset.order_by(
            models.F('deadline').desc(nulls_last=True),
            '-created_at'
        )
    
    # Standard field sorting
    valid_fields = ['created_at', 'status', 'title', 'updated_at']
    field = sort_param.lstrip('-')
    
    if field in valid_fields:
        return queryset.order_by(sort_param)
    
    # Default fallback
    return queryset.order_by('-created_at')


# Import models for F expression
from django.db import models
