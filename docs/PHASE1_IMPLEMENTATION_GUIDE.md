# Phase 1: Implementation Guide

**Task Management Application - Django 5.x**

This guide provides step-by-step instructions to implement Phase 1 on your local machine (macOS with VSCode).

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Project Setup](#project-setup)
3. [Create Project Files](#create-project-files)
4. [Initialize Database](#initialize-database)
5. [Verify Phase 1 Completeness](#verify-phase-1-completeness)
6. [GitHub Version Control Setup](#github-version-control-setup)

---

## Prerequisites

### 1. Check Python Version (3.12+ required)

```bash
python3 --version
```

If Python 3.12+ is not installed, install via Homebrew:
```bash
brew install python@3.12
```

### 2. Check pip
```bash
pip3 --version
```

### 3. Install PostgreSQL (optional for development)
For development, we use SQLite. PostgreSQL is needed for production.
```bash
# Optional: Install PostgreSQL
brew install postgresql@15
brew services start postgresql@15
```

---

## Project Setup

### Step 1: Create Project Directory

```bash
# Navigate to your development folder
cd ~/Documents  # or your preferred location

# Create project directory
mkdir task_manager
cd task_manager
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Your prompt should now show (venv)
```

### Step 3: Create requirements.txt

Create a file named `requirements.txt` in the project root:

```plaintext
# Django and core
Django>=5.0,<6.0
psycopg2-binary>=2.9.9
python-decouple>=3.8

# Authentication and security
argon2-cffi>=23.1.0

# HTMX integration
django-htmx>=1.17.0

# Filtering
django-filter>=24.0

# Image processing (for attachments)
Pillow>=10.0.0

# Background tasks
django-q2>=1.6.0

# Development tools
django-debug-toolbar>=4.2.0

# Testing
pytest>=8.0.0
pytest-django>=4.7.0
factory-boy>=3.3.0
```

### Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 5: Create .env File

Create a file named `.env` in the project root:

```plaintext
# Django Settings
SECRET_KEY=your-secret-key-here-change-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Configuration (PostgreSQL - for production)
DB_NAME=task_manager
DB_USER=postgres
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=5432

# Email Configuration (console backend for development)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=

# File Upload Settings
MAX_UPLOAD_SIZE_MB=2

# Session Settings
SESSION_IDLE_TIMEOUT_MINUTES=30
SESSION_ABSOLUTE_TIMEOUT_HOURS=8

# Security
LOCKOUT_THRESHOLD=5
LOCKOUT_DURATION_MINUTES=15
PASSWORD_EXPIRY_DAYS=90
```

### Step 6: Create .gitignore

Create a file named `.gitignore` in the project root:

```plaintext
# Virtual Environment
venv/
env/
.venv/

# Environment Variables
.env

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Django
*.log
local_settings.py
db.sqlite3
db.sqlite3-journal

# Static and Media files (local)
staticfiles/
media/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Testing
.coverage
htmlcov/
.pytest_cache/
.tox/

# Celery / Django-Q
celerybeat-schedule
celerybeat.pid

# Jupyter
.ipynb_checkpoints/
```

---

## Create Project Files

### Directory Structure

Create the following directory structure:

```bash
# Create all directories
mkdir -p config/settings
mkdir -p apps/accounts
mkdir -p apps/departments
mkdir -p apps/tasks
mkdir -p apps/activity_log
mkdir -p apps/reports
mkdir -p apps/notifications
mkdir -p templates/accounts
mkdir -p templates/tasks
mkdir -p templates/reports
mkdir -p templates/activity_log
mkdir -p static/css
mkdir -p static/js
mkdir -p media/attachments
mkdir -p docs
mkdir -p logs
```

### Create Files

You need to create the following files. I've listed them in the order they should be created:

---

#### 1. `manage.py` (Project Root)

```python
#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
```

---

#### 2. `config/__init__.py`

```python
"""Config package for task_manager project."""
```

---

#### 3. `config/settings/__init__.py`

```python
"""
Settings package for task_manager project.

By default, imports development settings.
For production, set DJANGO_SETTINGS_MODULE=config.settings.production
"""

# Default to development settings when importing from config.settings
from .development import *
```

---

#### 4. `config/settings/base.py`

```python
"""
Django base settings for task_manager project.
Shared settings between development and production.
"""

from pathlib import Path
from decouple import config, Csv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'django_htmx',
    'django_filters',
]

LOCAL_APPS = [
    'apps.accounts',
    'apps.departments',
    'apps.tasks',
    'apps.activity_log',
    'apps.reports',
    'apps.notifications',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# =============================================================================
# AUTHENTICATION - CRITICAL: Custom User Model
# =============================================================================
# Must be set BEFORE first migration
AUTH_USER_MODEL = 'accounts.User'

# Authentication backends
AUTHENTICATION_BACKENDS = [
    'apps.accounts.backends.EmailAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Login/Logout URLs
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'tasks:dashboard'
LOGOUT_REDIRECT_URL = 'accounts:login'


# =============================================================================
# PASSWORD VALIDATION
# =============================================================================
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 12,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
    {
        'NAME': 'apps.accounts.validators.ComplexityValidator',
    },
]

# Password hashing - use Argon2 as primary
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]


# =============================================================================
# INTERNATIONALIZATION & TIMEZONE
# =============================================================================
LANGUAGE_CODE = 'en-us'

# CRITICAL: Set to IST (Indian Standard Time) from day one
TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_TZ = True

# Date/Time formats for display (DD MMM YYYY, 12-hour)
DATE_FORMAT = 'j M Y'
TIME_FORMAT = 'g:i A'
DATETIME_FORMAT = 'j M Y, g:i A'
SHORT_DATE_FORMAT = 'd/m/Y'
SHORT_DATETIME_FORMAT = 'd/m/Y g:i A'


# =============================================================================
# STATIC & MEDIA FILES
# =============================================================================
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'


# =============================================================================
# FILE UPLOAD SETTINGS
# =============================================================================
# Maximum upload size: 2 MB
MAX_UPLOAD_SIZE = config('MAX_UPLOAD_SIZE_MB', default=2, cast=int) * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE

# Allowed file extensions for attachments
ALLOWED_UPLOAD_EXTENSIONS = [
    '.pdf', '.doc', '.docx', '.xls', '.xlsx',
    '.png', '.jpg', '.jpeg', '.txt'
]


# =============================================================================
# SESSION SETTINGS
# =============================================================================
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = config('SESSION_ABSOLUTE_TIMEOUT_HOURS', default=8, cast=int) * 3600
SESSION_IDLE_TIMEOUT = config('SESSION_IDLE_TIMEOUT_MINUTES', default=30, cast=int) * 60
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False


# =============================================================================
# SECURITY SETTINGS
# =============================================================================
# Account lockout settings
LOCKOUT_THRESHOLD = config('LOCKOUT_THRESHOLD', default=5, cast=int)
LOCKOUT_DURATION = config('LOCKOUT_DURATION_MINUTES', default=15, cast=int) * 60  # in seconds

# Password expiry
PASSWORD_EXPIRY_DAYS = config('PASSWORD_EXPIRY_DAYS', default=90, cast=int)

# Password history (cannot reuse last N passwords)
PASSWORD_HISTORY_COUNT = 5

# Allowed email domains for user registration
ALLOWED_EMAIL_DOMAINS = ['centuryextrusions.com', 'cnfcindia.com']


# =============================================================================
# EMAIL SETTINGS
# =============================================================================
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend'
)
EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')


# =============================================================================
# DJANGO-Q2 SETTINGS (Background Tasks)
# =============================================================================
Q_CLUSTER = {
    'name': 'task_manager',
    'workers': 2,
    'recycle': 500,
    'timeout': 60,
    'compress': True,
    'save_limit': 250,
    'queue_limit': 500,
    'cpu_affinity': 1,
    'label': 'Django Q2',
    'orm': 'default',
}


# =============================================================================
# DEFAULT PRIMARY KEY FIELD TYPE
# =============================================================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
```

---

#### 5. `config/settings/development.py`

```python
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
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


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
    },
}


# =============================================================================
# SECURITY (Relaxed for development)
# =============================================================================
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
```

---

#### 6. `config/settings/production.py`

```python
"""
Django production settings for task_manager project.
"""

from .base import *

# =============================================================================
# CORE SETTINGS
# =============================================================================
DEBUG = False

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='', cast=Csv())


# =============================================================================
# DATABASE - PostgreSQL for production
# =============================================================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'CONN_MAX_AGE': 60,
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}


# =============================================================================
# SECURITY SETTINGS
# =============================================================================
# HTTPS/SSL
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# HSTS (HTTP Strict Transport Security)
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Cookie security
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

# Content security
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# Referrer policy
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'


# =============================================================================
# EMAIL SETTINGS - Production SMTP
# =============================================================================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST')
EMAIL_PORT = config('EMAIL_PORT', cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')


# =============================================================================
# LOGGING
# =============================================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django_error.log',
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
        'django.security': {
            'handlers': ['security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
```

---

#### 7. `config/urls.py`

```python
"""
URL configuration for task_manager project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # App URLs
    path('', include('apps.accounts.urls', namespace='accounts')),
    path('tasks/', include('apps.tasks.urls', namespace='tasks')),
    path('departments/', include('apps.departments.urls', namespace='departments')),
    path('reports/', include('apps.reports.urls', namespace='reports')),
    path('activity/', include('apps.activity_log.urls', namespace='activity_log')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    
    # Debug toolbar
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns

# Admin site customization
admin.site.site_header = 'Task Manager Administration'
admin.site.site_title = 'Task Manager Admin'
admin.site.index_title = 'Welcome to Task Manager Admin'
```

---

#### 8. `config/wsgi.py`

```python
"""
WSGI config for task_manager project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

application = get_wsgi_application()
```

---

#### 9. `apps/__init__.py`

```python
"""Apps package for task_manager project."""
```

---

### App Files

Due to the length, I'll provide instructions to create each app. For the complete file contents, please refer to the project files directly or use the provided code snippets.

#### Create App __init__.py Files

Create empty `__init__.py` files in each app directory:

```bash
touch apps/accounts/__init__.py
touch apps/departments/__init__.py
touch apps/tasks/__init__.py
touch apps/activity_log/__init__.py
touch apps/reports/__init__.py
touch apps/notifications/__init__.py
```

---

### CRITICAL: accounts/models.py (Custom User Model)

This file MUST be created before running any migrations.

See the full file content in the project repository. Key points:
- Extends `AbstractUser`
- Uses email as the unique identifier (no username)
- Includes 5 roles: admin, senior_manager_1, senior_manager_2, manager, employee
- Security fields: failed_login_attempts, locked_until, password_history, must_change_password
- Permission helper methods

---

### Create Remaining App Files

For each app, you need to create:
- `models.py` - Database models
- `views.py` - View functions
- `urls.py` - URL patterns
- `admin.py` - Admin configuration
- `apps.py` - App configuration

**Important**: Copy the complete file contents from the source files provided earlier in this conversation.

---

## Initialize Database

### Step 1: Create Migrations

```bash
# Ensure virtual environment is active
source venv/bin/activate

# Create migrations for all apps
python manage.py makemigrations accounts
python manage.py makemigrations departments
python manage.py makemigrations tasks
python manage.py makemigrations activity_log

# Apply all migrations
python manage.py migrate
```

### Step 2: Create Superuser

```bash
python manage.py createsuperuser
```

When prompted:
- **Email**: admin@centuryextrusions.com
- **First name**: Admin
- **Last name**: User
- **Password**: AdminTest123! (or your preferred password meeting complexity requirements)

---

## Verify Phase 1 Completeness

Run these verification steps to confirm Phase 1 is complete:

### 1. Django System Check

```bash
python manage.py check
```

**Expected output**: `System check identified no issues (0 silenced).`

### 2. Migration Status

```bash
python manage.py showmigrations
```

**Expected output**: All migrations should show `[X]` indicating they're applied:
```
accounts
 [X] 0001_initial
 [X] 0002_initial
activity_log
 [X] 0001_initial
...
```

### 3. Start Development Server

```bash
python manage.py runserver
```

**Expected output**:
```
Watching for file changes with StatReloader
Performing system checks...

System check identified no issues (0 silenced).
December 25, 2025 - 12:00:00
Django version 5.x, using settings 'config.settings.development'
Starting development server at http://127.0.0.1:8000/
```

### 4. Access Admin Interface

1. Open browser to: http://127.0.0.1:8000/admin/
2. Login with superuser credentials
3. Verify you can see all models:
   - Users (under ACCOUNTS)
   - Departments (under DEPARTMENTS)
   - Tasks, Comments, Attachments (under TASKS)
   - Task activities (under ACTIVITY_LOG)

### 5. Test Authentication Backend

```bash
python manage.py shell
```

In the shell:
```python
from apps.accounts.models import User
from django.contrib.auth import authenticate

# Test user exists
user = User.objects.get(email='admin@centuryextrusions.com')
print(f"User: {user}")
print(f"Role: {user.role}")
print(f"Is Admin: {user.is_admin()}")

# Test authentication
authenticated = authenticate(username='admin@centuryextrusions.com', password='AdminTest123!')
print(f"Authentication: {'Success' if authenticated else 'Failed'}")

exit()
```

### 6. Verify Timezone Setting

```bash
python manage.py shell
```

```python
from django.conf import settings
print(f"Timezone: {settings.TIME_ZONE}")
# Expected: Asia/Kolkata

from django.utils import timezone
print(f"Current time: {timezone.now()}")

exit()
```

### 7. Phase 1 Checklist

| Item | Status |
|------|--------|
| Project structure created | ☐ |
| Virtual environment active | ☐ |
| Dependencies installed | ☐ |
| Split settings (base/dev/prod) | ☐ |
| Custom User model defined | ☐ |
| AUTH_USER_MODEL set before migrations | ☐ |
| All apps created | ☐ |
| All migrations applied | ☐ |
| Superuser created | ☐ |
| Development server runs | ☐ |
| Admin interface accessible | ☐ |
| IST timezone configured | ☐ |

---

## GitHub Version Control Setup

### Step 1: Initialize Git Repository

```bash
# Navigate to project root
cd ~/Documents/task_manager  # or your project location

# Initialize git repository
git init
```

### Step 2: Verify .gitignore

Ensure `.gitignore` exists and includes:
- `venv/`
- `.env`
- `db.sqlite3`
- `media/`
- `__pycache__/`
- `staticfiles/`

### Step 3: Initial Commit

```bash
# Add all files
git add .

# Check what will be committed
git status

# Make initial commit
git commit -m "Phase 1: Project foundation and setup

- Django project structure with split settings
- Custom User model with email authentication
- 5 user roles: Admin, SM1, SM2, Manager, Employee
- Department, Task, Comment, Attachment models
- Activity log model for audit trails
- IST timezone configuration
- Password validators and security settings
- Admin interface configuration
- Base template with Tailwind CSS and HTMX"
```

### Step 4: Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `task-manager`
3. Description: "Internal task management application - Django 5.x"
4. Visibility: **Private** (recommended for internal apps)
5. Do NOT initialize with README, .gitignore, or license (we already have these)
6. Click "Create repository"

### Step 5: Connect Local to GitHub

```bash
# Add remote origin (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/task-manager.git

# Verify remote
git remote -v

# Push to GitHub
git branch -M main
git push -u origin main
```

### Step 6: Verify on GitHub

1. Refresh your GitHub repository page
2. Verify all files are present
3. Check that `.env` and `db.sqlite3` are NOT present (they should be gitignored)

### Step 7: Recommended Branch Strategy

For ongoing development:

```bash
# Create development branch
git checkout -b development

# Push development branch
git push -u origin development
```

**Branch workflow:**
- `main` - Production-ready code
- `development` - Active development
- `feature/phase-X-description` - Feature branches for each phase

### Step 8: Create Phase 2 Branch (Optional)

```bash
# When starting Phase 2:
git checkout development
git pull origin development
git checkout -b feature/phase-2-authentication

# After completing Phase 2:
git add .
git commit -m "Phase 2: Authentication & Security implementation"
git push origin feature/phase-2-authentication

# Create Pull Request on GitHub to merge into development
```

---

## Next Steps

Phase 1 is now complete. Proceed to:

1. **Phase 2: Data Models & Migrations** - Verify and enhance existing models
2. **Phase 3: Authentication & Security** - Build login views, password change flows, session middleware

Refer to `task_manager_implementation_plan.md` for detailed phase instructions.

---

## Troubleshooting

### Common Issues

**1. ModuleNotFoundError: No module named 'decouple'**
```bash
pip install python-decouple
```

**2. Migration errors about AUTH_USER_MODEL**
- This happens if you run migrations before creating the User model
- Solution: Delete `db.sqlite3` and all migration files, then recreate

**3. Template not found errors**
- Ensure `templates/` directory is in project root
- Verify `TEMPLATES['DIRS']` in settings includes `BASE_DIR / 'templates'`

**4. Static files not loading**
- Ensure `static/` directory exists
- Run `python manage.py collectstatic` for production

---

## Support

For issues or questions about this implementation:
1. Review the project documentation
2. Check Django's official documentation
3. Consult the implementation plan document

---

*Document created: December 2025*
*Phase 1 Implementation Guide v1.0*
