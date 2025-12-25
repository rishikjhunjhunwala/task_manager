"""
Custom User model for task_manager.

CRITICAL: This file must be created and AUTH_USER_MODEL set before running
any migrations. Changing the User model after migrations is very complex.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """
    Custom user manager where email is the unique identifier
    for authentication instead of username.
    """

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user with the given email and password."""
        if not email:
            raise ValueError('The Email field must be set')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', User.Role.ADMIN)
        extra_fields.setdefault('must_change_password', False)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom User model with email authentication and role-based access.
    
    Roles:
    - Admin: Full access, user management, system config, activity logs
    - Senior Manager 1: Assign to anyone, view all, receives 120-hour escalations
    - Senior Manager 2: Assign to anyone, view all, receives 72-hour escalations
    - Manager: Assign within department, view department tasks
    - Employee: Create personal tasks, view own tasks only
    """

    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        SENIOR_MANAGER_1 = 'senior_manager_1', 'Senior Manager 1'
        SENIOR_MANAGER_2 = 'senior_manager_2', 'Senior Manager 2'
        MANAGER = 'manager', 'Manager'
        EMPLOYEE = 'employee', 'Employee'

    # Remove username field, use email instead
    username = None
    email = models.EmailField(
        'email address',
        unique=True,
        error_messages={
            'unique': 'A user with that email already exists.',
        },
    )

    # Role and department
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.EMPLOYEE,
        db_index=True,
    )
    department = models.ForeignKey(
        'departments.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )

    # Security fields
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    must_change_password = models.BooleanField(
        default=True,
        help_text='If True, user must change password on next login.',
    )
    password_history = models.JSONField(
        default=list,
        blank=True,
        help_text='Stores hashes of last 5 passwords to prevent reuse.',
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'
        ordering = ['first_name', 'last_name']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role']),
            models.Index(fields=['department']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"

    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between."""
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name or self.email

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name or self.email.split('@')[0]

    # ==========================================================================
    # Account Status Methods
    # ==========================================================================

    def is_locked(self):
        """Check if the account is currently locked."""
        if self.locked_until and self.locked_until > timezone.now():
            return True
        return False

    def lock_account(self, duration_seconds):
        """Lock the account for the specified duration."""
        self.locked_until = timezone.now() + timezone.timedelta(seconds=duration_seconds)
        self.save(update_fields=['locked_until'])

    def unlock_account(self):
        """Unlock the account and reset failed attempts."""
        self.locked_until = None
        self.failed_login_attempts = 0
        self.save(update_fields=['locked_until', 'failed_login_attempts'])

    def record_failed_login(self):
        """Record a failed login attempt."""
        self.failed_login_attempts += 1
        self.save(update_fields=['failed_login_attempts'])

    def reset_failed_logins(self):
        """Reset failed login counter on successful login."""
        if self.failed_login_attempts > 0:
            self.failed_login_attempts = 0
            self.save(update_fields=['failed_login_attempts'])

    # ==========================================================================
    # Password Methods
    # ==========================================================================

    def is_password_expired(self):
        """Check if the password has expired (90 days)."""
        from django.conf import settings
        
        if not self.password_changed_at:
            return True
        
        expiry_days = getattr(settings, 'PASSWORD_EXPIRY_DAYS', 90)
        expiry_date = self.password_changed_at + timezone.timedelta(days=expiry_days)
        return timezone.now() > expiry_date

    def add_password_to_history(self, password_hash):
        """Add a password hash to history, keeping only last 5."""
        from django.conf import settings
        
        history_count = getattr(settings, 'PASSWORD_HISTORY_COUNT', 5)
        history = self.password_history or []
        history.insert(0, password_hash)
        self.password_history = history[:history_count]

    def is_password_in_history(self, password):
        """Check if password matches any in history."""
        from django.contrib.auth.hashers import check_password
        
        for old_hash in (self.password_history or []):
            if check_password(password, old_hash):
                return True
        return False

    # ==========================================================================
    # Role Permission Methods
    # ==========================================================================

    def is_admin(self):
        """Check if user is an Admin."""
        return self.role == self.Role.ADMIN

    def is_senior_manager(self):
        """Check if user is any Senior Manager level."""
        return self.role in [self.Role.SENIOR_MANAGER_1, self.Role.SENIOR_MANAGER_2]

    def is_senior_manager_1(self):
        """Check if user is Senior Manager 1."""
        return self.role == self.Role.SENIOR_MANAGER_1

    def is_senior_manager_2(self):
        """Check if user is Senior Manager 2."""
        return self.role == self.Role.SENIOR_MANAGER_2

    def is_manager(self):
        """Check if user is a Manager."""
        return self.role == self.Role.MANAGER

    def is_employee(self):
        """Check if user is an Employee."""
        return self.role == self.Role.EMPLOYEE

    def can_assign_to_anyone(self):
        """Check if user can assign tasks to any user."""
        return self.role in [
            self.Role.ADMIN,
            self.Role.SENIOR_MANAGER_1,
            self.Role.SENIOR_MANAGER_2,
        ]

    def can_assign_in_department(self):
        """Check if user can assign tasks within their department."""
        return self.role == self.Role.MANAGER

    def can_view_all_tasks(self):
        """Check if user can view all tasks across departments."""
        return self.role in [
            self.Role.ADMIN,
            self.Role.SENIOR_MANAGER_1,
            self.Role.SENIOR_MANAGER_2,
        ]

    def can_view_department_tasks(self):
        """Check if user can view all tasks in their department."""
        return self.role == self.Role.MANAGER

    def can_view_activity_log(self):
        """Check if user can access the activity log."""
        return self.role == self.Role.ADMIN

    def can_manage_users(self):
        """Check if user can manage other users."""
        return self.role == self.Role.ADMIN
