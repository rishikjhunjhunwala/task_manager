"""
Settings package for task_manager project.

By default, imports development settings.
For production, set DJANGO_SETTINGS_MODULE=config.settings.production
"""

# Default to development settings when importing from config.settings
from .development import *
