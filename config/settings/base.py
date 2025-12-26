"""
Django base settings for task_manager project.
Shared settings between development and production.

Updated for Phase 3: Authentication & Security
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
    # Phase 3: Custom session management middleware
    'apps.accounts.middleware.SessionIdleTimeoutMiddleware',
    'apps.accounts.middleware.PasswordChangeRequiredMiddleware',
    'apps.accounts.middleware.PasswordExpiryMiddleware',
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
    # Phase 3: Password history validator (applied during password change)
    # Note: PasswordHistoryValidator requires user context, so it's applied in forms
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
# SESSION SETTINGS (Phase 3)
# =============================================================================
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# Absolute session timeout: 8 hours (from login time)
SESSION_COOKIE_AGE = config('SESSION_ABSOLUTE_TIMEOUT_HOURS', default=8, cast=int) * 3600

# Idle timeout: 30 minutes (resets on each request)
SESSION_IDLE_TIMEOUT = config('SESSION_IDLE_TIMEOUT_MINUTES', default=30, cast=int) * 60

# Save session on every request (needed for idle timeout tracking)
SESSION_SAVE_EVERY_REQUEST = True

# Don't expire session when browser closes (we handle timeout ourselves)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False


# =============================================================================
# SECURITY SETTINGS (Phase 3)
# =============================================================================
# Account lockout settings
LOCKOUT_THRESHOLD = config('LOCKOUT_THRESHOLD', default=5, cast=int)
LOCKOUT_DURATION = config('LOCKOUT_DURATION_MINUTES', default=15, cast=int) * 60  # in seconds

# Password expiry (90 days)
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

# Default from email (for welcome emails, etc.)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@centuryextrusions.com')

# Support email for user assistance
SUPPORT_EMAIL = config('SUPPORT_EMAIL', default='admin@centuryextrusions.com')

# Site URL (for email links)
SITE_URL = config('SITE_URL', default='http://localhost:8000')


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
