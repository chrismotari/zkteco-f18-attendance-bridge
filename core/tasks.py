"""
Celery tasks for attendance bridge.

This module defines periodic tasks for:
- Polling devices for attendance logs
- Processing raw attendance data
- Syncing processed attendance to CRM
"""
import logging
from datetime import datetime, timedelta
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from .device_utils import poll_all_devices
from .processing_utils import process_all_unprocessed_attendance, process_attendance_for_date_range
from .crm_utils import sync_unsynced_attendance, retry_failed_syncs

logger = logging.getLogger('core')


@shared_task(name='core.poll_devices')
def poll_devices_task():
    """
    Periodic task to poll all enabled devices for attendance logs.
    
    This task should run every X minutes (configured in Celery Beat).
    """
    logger.info("Starting device polling task")
    
    try:
        # Poll all devices
        results = poll_all_devices()
        
        logger.info(f"Device polling completed: {results['successful']} devices polled successfully, "
                   f"{results['failed']} failed")
        
        return {
            'status': 'success',
            'results': results,
            'timestamp': timezone.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error in device polling task: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name='core.process_attendance')
def process_attendance_task():
    """
    Periodic task to process raw attendance data.
    
    This task should run hourly or daily (configured in Celery Beat).
    """
    logger.info("Starting attendance processing task")
    
    try:
        # Process all unprocessed attendance
        results = process_all_unprocessed_attendance()
        
        logger.info(f"Attendance processing completed: {results['processed']} records processed, "
                   f"{results['outliers']} outliers detected, {results['failed']} failed")
        
        return {
            'status': 'success',
            'results': results,
            'timestamp': timezone.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error in attendance processing task: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name='core.sync_to_crm')
def sync_to_crm_task(limit=None):
    """
    Periodic task to sync processed attendance to CRM.
    
    Args:
        limit: Maximum number of records to sync (uses settings default if not provided)
    
    This task should run regularly (configured in Celery Beat).
    """
    logger.info("Starting CRM sync task")
    
    try:
        # Sync unsynced attendance
        results = sync_unsynced_attendance(limit=limit)
        
        logger.info(f"CRM sync completed: {results['successful']} records synced, "
                   f"{results['failed']} failed")
        
        return {
            'status': 'success',
            'results': results,
            'timestamp': timezone.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error in CRM sync task: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name='core.retry_failed_syncs')
def retry_failed_syncs_task():
    """
    Periodic task to retry failed CRM syncs.
    
    This task should run less frequently (e.g., daily).
    """
    logger.info("Starting retry failed syncs task")
    
    try:
        # Retry failed syncs
        results = retry_failed_syncs(max_attempts=settings.CRM_MAX_RETRIES)
        
        logger.info(f"Retry failed syncs completed: {results['successful']} records synced, "
                   f"{results['failed']} still failed")
        
        return {
            'status': 'success',
            'results': results,
            'timestamp': timezone.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error in retry failed syncs task: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name='core.daily_cleanup')
def daily_cleanup_task():
    """
    Daily cleanup task to remove old data and optimize database.
    
    This task should run daily during off-peak hours.
    """
    logger.info("Starting daily cleanup task")
    
    from .models import RawAttendance, ProcessedAttendance
    from django.db.models import Count
    
    results = {
        'old_raw_deleted': 0,
        'duplicates_removed': 0
    }
    
    try:
        # Remove raw attendance older than 90 days (configurable)
        cutoff_date = timezone.now() - timedelta(days=90)
        old_raw = RawAttendance.objects.filter(timestamp__lt=cutoff_date)
        results['old_raw_deleted'] = old_raw.count()
        old_raw.delete()
        logger.info(f"Deleted {results['old_raw_deleted']} old raw attendance records")
        
        # Remove duplicates (shouldn't happen, but just in case)
        from .processing_utils import deduplicate_records
        dedup_results = deduplicate_records()
        results['duplicates_removed'] = dedup_results['records_removed']
        
        logger.info("Daily cleanup completed successfully")
        
        return {
            'status': 'success',
            'results': results,
            'timestamp': timezone.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error in daily cleanup task: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name='core.process_date_range')
def process_date_range_task(start_date_str: str, end_date_str: str = None):
    """
    Task to process attendance for a specific date range.
    Can be called manually or scheduled.
    
    Args:
        start_date_str: Start date in YYYY-MM-DD format
        end_date_str: End date in YYYY-MM-DD format (optional)
    """
    from datetime import date
    
    logger.info(f"Processing attendance for date range: {start_date_str} to {end_date_str or 'today'}")
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
        
        results = process_attendance_for_date_range(start_date, end_date)
        
        logger.info(f"Date range processing completed: {results['processed']} records processed")
        
        return {
            'status': 'success',
            'results': results,
            'timestamp': timezone.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error in process date range task: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }
