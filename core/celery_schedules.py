"""
Celery Beat schedule configuration.

This module defines the periodic task schedule for Celery Beat.
Import this in your settings.py or configure via Django Celery Beat admin.
"""
from celery.schedules import crontab
from django.conf import settings

# Celery Beat Schedule
CELERY_BEAT_SCHEDULE = {
    # Poll devices every X minutes (from settings)
    'poll-devices': {
        'task': 'core.poll_devices',
        'schedule': settings.POLLING_INTERVAL_MINUTES * 60.0,  # Convert to seconds
        'options': {
            'expires': settings.POLLING_INTERVAL_MINUTES * 60 - 10,  # Expire 10 seconds before next run
        }
    },
    
    # Process attendance hourly
    'process-attendance': {
        'task': 'core.process_attendance',
        'schedule': crontab(minute=5),  # Run at 5 minutes past every hour
    },
    
    # Sync to CRM every 30 minutes
    'sync-to-crm': {
        'task': 'core.sync_to_crm',
        'schedule': 30 * 60.0,  # Every 30 minutes
        'options': {
            'expires': 25 * 60,  # Expire after 25 minutes
        }
    },
    
    # Retry failed syncs every 6 hours
    'retry-failed-syncs': {
        'task': 'core.retry_failed_syncs',
        'schedule': crontab(minute=30, hour='*/6'),  # Every 6 hours at :30
    },
    
    # Daily cleanup at 2 AM
    'daily-cleanup': {
        'task': 'core.daily_cleanup',
        'schedule': crontab(minute=0, hour=2),  # Daily at 2:00 AM
    },
}
