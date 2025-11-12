"""
Celery configuration for attendance_bridge project.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_bridge.settings')

app = Celery('attendance_bridge')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Configure Celery Beat schedule
from django.conf import settings

app.conf.beat_schedule = {
    'poll-devices': {
        'task': 'core.poll_devices',
        'schedule': settings.POLLING_INTERVAL_MINUTES * 60.0,
        'options': {
            'expires': settings.POLLING_INTERVAL_MINUTES * 60 - 10,
        }
    },
    'process-attendance': {
        'task': 'core.process_attendance',
        'schedule': crontab(minute=5),
    },
    'sync-to-crm': {
        'task': 'core.sync_to_crm',
        'schedule': 30 * 60.0,
        'options': {
            'expires': 25 * 60,
        }
    },
    'retry-failed-syncs': {
        'task': 'core.retry_failed_syncs',
        'schedule': crontab(minute=30, hour='*/6'),
    },
    'daily-cleanup': {
        'task': 'core.daily_cleanup',
        'schedule': crontab(minute=0, hour=2),
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
