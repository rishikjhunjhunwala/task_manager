"""
Django development settings for task_manager project.
"""

from .base import *

# =============================================================================
# CORE SETTINGS
# =============================================================================
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']


# =============================================================================
# DATABASE - SQLite for development (PostgreSQL recommended for production)
# =============================================================================
# For quick local development, use SQLite
# Switch to PostgreSQL for testing production-like behavior

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Uncomment below to use PostgreSQL in development
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': config('DB_NAME', default='task_manager'),
#         'USER': config('DB_USER', default='postgres'),
#         'PASSWORD': config('DB_PASSWORD', default=''),
#         'HOST': config('DB_HOST', default='localhost'),
#         'PORT': config('DB_PORT', default='5432'),
#     }
# }


# =============================================================================
# DEBUG TOOLBAR (Development only)
# =============================================================================
INSTALLED_APPS += ['debug_toolbar']

MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')

INTERNAL_IPS = ['127.0.0.1', 'localhost']

DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': lambda request: DEBUG,
}


# =============================================================================
# EMAIL - Console backend for development
# =============================================================================
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


# =============================================================================
# LOGGING
# =============================================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'email_file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'email.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'email_file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'email.log',
            'formatter': 'verbose',
        },
    },
}


# =============================================================================
# SECURITY (Relaxed for development)
# =============================================================================
# These are intentionally relaxed for development
# Production settings will enable these properly
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
