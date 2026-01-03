"""
Activity log filters using django-filter.

Provides filtering capabilities for the activity log view:
- Task filter (dropdown)
- User filter (dropdown)
- Action type filter (dropdown)
- Date range filters (from/to)
"""

import django_filters
from django import forms
from django.utils import timezone
from datetime import timedelta

from .models import TaskActivity
from apps.tasks.models import Task
from apps.accounts.models import User


class ActivityFilter(django_filters.FilterSet):
    """
    Filter for activity log entries.
    
    Usage:
        filterset = ActivityFilter(request.GET, queryset=queryset)
        activities = filterset.qs
    """
    
    # Task filter
    task = django_filters.ModelChoiceFilter(
        queryset=Task.objects.all(),
        label='Task',
        empty_label='All Tasks',
        widget=forms.Select(attrs={
            'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        })
    )
    
    # User filter
    user = django_filters.ModelChoiceFilter(
        queryset=User.objects.filter(is_active=True),
        label='User',
        empty_label='All Users',
        widget=forms.Select(attrs={
            'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        })
    )
    
    # Action type filter
    action_type = django_filters.ChoiceFilter(
        choices=[('', 'All Actions')] + list(TaskActivity.ActionType.choices),
        label='Action Type',
        empty_label=None,
        widget=forms.Select(attrs={
            'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        })
    )
    
    # Date from filter
    date_from = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='gte',
        label='Date From',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        })
    )
    
    # Date to filter
    date_to = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='lte',
        label='Date To',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        })
    )

    class Meta:
        model = TaskActivity
        fields = ['task', 'user', 'action_type']

    def __init__(self, data=None, queryset=None, **kwargs):
        """Initialize filter with optimized querysets."""
        super().__init__(data, queryset, **kwargs)
        
        # Optimize task queryset - only show tasks with activities
        self.filters['task'].queryset = Task.objects.filter(
            activities__isnull=False
        ).distinct().order_by('-created_at')
        
        # Optimize user queryset - only show users who have performed activities
        self.filters['user'].queryset = User.objects.filter(
            task_activities__isnull=False
        ).distinct().order_by('first_name', 'last_name')