"""
Views for departments app.

Includes:
- Department list view
- Department create view
- Department edit view

All views are admin-only.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q

from .models import Department
from .forms import DepartmentForm


def admin_required(view_func):
    """Decorator to require admin role."""
    def check_admin(user):
        return user.is_authenticated and user.role == 'admin'
    
    decorated_view = user_passes_test(check_admin, login_url='accounts:login')(view_func)
    return decorated_view


@login_required
@admin_required
def department_list_view(request):
    """
    List all departments with employee counts.
    Admin only.
    """
    departments = Department.objects.select_related('head').annotate(
        active_employee_count=Count('users', filter=Q(users__is_active=True)),
        total_employee_count=Count('users')
    ).order_by('name')
    
    # Search
    search = request.GET.get('search', '').strip()
    if search:
        departments = departments.filter(
            Q(name__icontains=search) |
            Q(code__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(departments, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'departments': page_obj,
        'search': search,
        'total_count': paginator.count,
    }
    return render(request, 'departments/department_list.html', context)


@login_required
@admin_required
def department_create_view(request):
    """
    Create a new department.
    Admin only.
    """
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            department = form.save()
            messages.success(
                request,
                f'Department "{department.name}" ({department.code}) created successfully.'
            )
            return redirect('departments:department_list')
    else:
        form = DepartmentForm()
    
    return render(request, 'departments/department_form.html', {
        'form': form,
        'is_edit': False,
        'title': 'Create Department',
    })


@login_required
@admin_required
def department_edit_view(request, pk):
    """
    Edit an existing department.
    Admin only.
    """
    department = get_object_or_404(Department, pk=pk)
    
    # Get department statistics
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    stats = {
        'active_users': User.objects.filter(department=department, is_active=True).count(),
        'total_users': User.objects.filter(department=department).count(),
    }
    
    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            department = form.save()
            messages.success(
                request,
                f'Department "{department.name}" updated successfully.'
            )
            return redirect('departments:department_list')
    else:
        form = DepartmentForm(instance=department)
    
    return render(request, 'departments/department_form.html', {
        'form': form,
        'is_edit': True,
        'department': department,
        'title': f'Edit Department: {department.name}',
        'stats': stats,
    })


@login_required
@admin_required
def department_detail_view(request, pk):
    """
    View department details with user list.
    Admin only.
    """
    department = get_object_or_404(Department, pk=pk)
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    users = User.objects.filter(department=department).order_by('-is_active', 'first_name', 'last_name')
    
    # Pagination for users
    paginator = Paginator(users, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'department': department,
        'page_obj': page_obj,
        'users': page_obj,
        'active_count': users.filter(is_active=True).count(),
        'total_count': users.count(),
    }
    return render(request, 'departments/department_detail.html', context)
