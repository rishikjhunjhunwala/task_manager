"""
Department model for organizational structure.

Departments are flat (no hierarchy/nesting).
Department head must be Manager, Senior Manager 1, or Senior Manager 2.
"""

from django.db import models
from django.conf import settings


class Department(models.Model):
    """
    Represents an organizational department.
    
    Notes:
    - Departments are flat (no parent/child relationships)
    - Head must be Manager or Senior Manager level
    - Code is a short identifier (e.g., "ENG", "HR")
    """
    
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text='Full department name'
    )
    code = models.CharField(
        max_length=10,
        unique=True,
        help_text='Short identifier (e.g., ENG, HR, FIN)'
    )
    head = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_departments',
        help_text='Department head (must be Manager or Senior Manager)'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'department'
        verbose_name_plural = 'departments'
        ordering = ['name']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def clean(self):
        """Validate that head is appropriate role."""
        from django.core.exceptions import ValidationError
        
        if self.head:
            allowed_roles = ['manager', 'senior_manager_1', 'senior_manager_2']
            if self.head.role not in allowed_roles:
                raise ValidationError({
                    'head': 'Department head must be a Manager or Senior Manager.'
                })

    def save(self, *args, **kwargs):
        # Ensure code is uppercase
        if self.code:
            self.code = self.code.upper()
        super().save(*args, **kwargs)

    @property
    def employee_count(self):
        """Return the number of active users in this department."""
        return self.users.filter(is_active=True).count()
