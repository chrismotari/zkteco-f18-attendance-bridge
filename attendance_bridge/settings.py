"""
Django settings for attendance_bridge project.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-change-this-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'django_celery_beat',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'attendance_bridge.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'attendance_bridge.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': f'django.db.backends.{os.getenv("DB_ENGINE", "sqlite3")}',
        'NAME': os.getenv('DB_NAME', str(BASE_DIR / 'db.sqlite3')),
        'USER': os.getenv('DB_USER', ''),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', ''),
        'PORT': os.getenv('DB_PORT', ''),
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.getenv('TIME_ZONE', 'UTC')
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Celery Configuration
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'attendance_bridge.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'core': {
            'handlers': ['console', 'file'],
            'level': os.getenv('LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'django': {
            'handlers': ['console'],
            'level': os.getenv('LOG_LEVEL', 'INFO'),
        },
    },
}

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
}

# Custom Application Settings
# ZKTeco Device Configuration
ZKTECO_DEFAULT_PORT = int(os.getenv('ZKTECO_DEFAULT_PORT', '4370'))
ZKTECO_TIMEOUT = int(os.getenv('ZKTECO_TIMEOUT', '10'))

# Default timezone for devices (used when device timestamps are in device-local time).
# Set via environment variable DEVICE_TIME_ZONE (e.g. 'Africa/Nairobi' for EAT devices).
DEVICE_TIME_ZONE = os.getenv('DEVICE_TIME_ZONE', 'Africa/Nairobi')

# Display timezone for frontend (used for showing timestamps to users)
DISPLAY_TIMEZONE = os.getenv('DISPLAY_TIMEZONE', 'Africa/Nairobi')

# Polling Configuration
POLLING_INTERVAL_MINUTES = int(os.getenv('POLLING_INTERVAL_MINUTES', '15'))

# Work Hours Configuration
WORK_START_TIME = os.getenv('WORK_START_TIME', '08:00')
WORK_END_TIME = os.getenv('WORK_END_TIME', '18:00')
OVERNIGHT_SHIFT = os.getenv('OVERNIGHT_SHIFT', 'False').lower() == 'true'
OVERNIGHT_SHIFT_BUFFER_HOURS = int(os.getenv('OVERNIGHT_SHIFT_BUFFER_HOURS', '2'))

# Late/Early Detection Configuration (in hours)
LATE_CLOCK_IN_BUFFER_HOURS = int(os.getenv('LATE_CLOCK_IN_BUFFER_HOURS', '2'))
EARLY_CLOCK_OUT_BUFFER_HOURS = int(os.getenv('EARLY_CLOCK_OUT_BUFFER_HOURS', '2'))

# Outlier Detection Configuration (in hours)
OUTLIER_EARLY_CLOCK_IN_HOURS = int(os.getenv('OUTLIER_EARLY_CLOCK_IN_HOURS', '2'))
OUTLIER_LATE_CLOCK_IN_HOURS = int(os.getenv('OUTLIER_LATE_CLOCK_IN_HOURS', '2'))
OUTLIER_EARLY_CLOCK_OUT_HOURS = int(os.getenv('OUTLIER_EARLY_CLOCK_OUT_HOURS', '2'))
OUTLIER_LATE_CLOCK_OUT_HOURS = int(os.getenv('OUTLIER_LATE_CLOCK_OUT_HOURS', '3'))

# CRM Configuration
CRM_API_URL = os.getenv('CRM_API_URL', '')
CRM_API_TOKEN = os.getenv('CRM_API_TOKEN', '')
CRM_SYNC_BATCH_SIZE = int(os.getenv('CRM_SYNC_BATCH_SIZE', '100'))
CRM_REQUEST_TIMEOUT = int(os.getenv('CRM_REQUEST_TIMEOUT', '30'))
CRM_MAX_RETRIES = int(os.getenv('CRM_MAX_RETRIES', '3'))
