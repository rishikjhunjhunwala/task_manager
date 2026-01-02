"""
Activity log filters using django-filter.

Provides filtering capabilities for the activity log view (Admin only):
- Task filter (dropdown by reference number)
- User filter (dropdown of users who performed actions)
- Action Type filter (choices from TaskActivity.ActionType)
- Date Range filter (from date, to date)
"""

import django_filters
from django import forms
from django.db.models import Q

from .models import TaskActivity
from apps.accounts.models import User
from apps.tasks.models import Task


class ActivityFilter(django_filters.FilterSet):
    """
    Filter for activity log view.
    
    Admin-only view with the following filters:
    - task: Select task by reference number
    - user: Select user who performed the action
    - action_type: Filter by action type
    - date_from: Activities on or after this date
    - date_to: Activities on or before this date
    
    Usage in views:
        filterset = ActivityFilter(request.GET, queryset=queryset)
        activities = filterset.qs
    """
    
    # Task filter - dropdown ordered by reference number (newest first)
    task = django_filters.ModelChoiceFilter(
        queryset=Task.objects.all().order_by('-reference_number'),
        label='Task',
        empty_label='All Tasks',
        to_field_name='id',
        widget=forms.Select(attrs={
            'class': 'block w-full rounded-md border-gray-300 shadow-sm '
                     'focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        })
    )
    
    # User filter - users who have performed actions (optimized query)
    user = django_filters.ModelChoiceFilter(
        queryset=User.objects.none(),  # Set dynamically in __init__
        label='User',
        empty_label='All Users',
        widget=forms.Select(attrs={
            'class': 'block w-full rounded-md border-gray-300 shadow-sm '
                     'focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        })
    )
    
    # Action type filter - uses model's ActionType choices
    action_type = django_filters.ChoiceFilter(
        choices=[('', 'All Actions')] + list(TaskActivity.ActionType.choices),
        label='Action Type',
        empty_label=None,
        widget=forms.Select(attrs={
            'class': 'block w-full rounded-md border-gray-300 shadow-sm '
                     'focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        })
    )
    
    # Date range - from date
    date_from = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='date__gte',
        label='From Date',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'block w-full rounded-md border-gray-300 shadow-sm '
                     'focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        })
    )
    
    # Date range - to date
    date_to = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='date__lte',
        label='To Date',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'block w-full rounded-md border-gray-300 shadow-sm '
                     'focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        })
    )
    
    # Search filter - search in description, task reference, user name
    search = django_filters.CharFilter(
        method='filter_search',
        label='Search',
        widget=forms.TextInput(attrs={
            'placeholder': 'Search activities...',
            'class': 'block w-full rounded-md border-gray-300 shadow-sm '
                     'focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        })
    )

    class Meta:
        model = TaskActivity
        fields = ['task', 'user', 'action_type', 'date_from', 'date_to', 'search']

    def __init__(self, data=None, queryset=None, **kwargs):
        """
        Initialize filter with optimized querysets.
        
        - Task dropdown shows tasks ordered by reference number (newest first)
        - User dropdown shows only users who have activity records
        """
        super().__init__(data, queryset, **kwargs)
        
        # Optimize task queryset - only show tasks that have activity records
        # and display reference_number in dropdown
        tasks_with_activity = TaskActivity.objects.values_list(
            'task_id', flat=True
        ).distinct()
        self.filters['task'].queryset = Task.objects.filter(
            id__in=tasks_with_activity
        ).order_by('-reference_number')
        
        # Optimize user queryset - only show users who have performed actions
        users_with_activity = TaskActivity.objects.values_list(
            'user_id', flat=True
        ).distinct()
        self.filters['user'].queryset = User.objects.filter(
            id__in=users_with_activity
        ).order_by('first_name', 'last_name')

    def filter_search(self, queryset, name, value):
        """
        Search across description, task reference number, and user name.
        Case-insensitive partial matching.
        """
        if not value:
            return queryset
        
        return queryset.filter(
            Q(description__icontains=value) |
            Q(task__reference_number__icontains=value) |
            Q(task__title__icontains=value) |
            Q(user__first_name__icontains=value) |
            Q(user__last_name__icontains=value) |
            Q(user__email__icontains=value)
        )

    @property
    def is_filtered(self):
        """
        Check if any filters are actively applied.
        Useful for showing "clear filters" button in template.
        """
        if not self.data:
            return False
        
        # Check if any filter has a non-empty value
        for field_name in self.filters.keys():
            value = self.data.get(field_name, '')
            if value and value.strip():
                return True
        return False