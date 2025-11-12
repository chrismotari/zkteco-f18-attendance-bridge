"""
CRM synchronization utilities.

This module provides functions to:
- Sync processed attendance to remote CRM system
- Handle authentication and retries
- Batch sync support
- Error handling and logging
"""
import logging
import time
from typing import List, Dict, Tuple, Optional
from datetime import date
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from django.conf import settings
from django.utils import timezone
from .models import ProcessedAttendance

logger = logging.getLogger('core')


def get_session_with_retries() -> requests.Session:
    """
    Create a requests session with automatic retry logic.
    
    Returns:
        Configured requests.Session object
    """
    session = requests.Session()
    
    # Configure retry strategy
    retry_strategy = Retry(
        total=settings.CRM_MAX_RETRIES,
        backoff_factor=1,  # Wait 1, 2, 4 seconds between retries
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session


def prepare_attendance_data(attendance: ProcessedAttendance) -> dict:
    """
    Prepare attendance record for CRM API.
    
    Args:
        attendance: ProcessedAttendance instance
    
    Returns:
        Dictionary formatted for CRM API
    """
    data = {
        'user_id': attendance.user_id,
        'date': attendance.date.isoformat(),
        'clock_in': attendance.clock_in.isoformat() if attendance.clock_in else None,
        'clock_out': attendance.clock_out.isoformat() if attendance.clock_out else None,
        'is_outlier': attendance.is_outlier,
        'outlier_reason': attendance.outlier_reason,
        'device_name': attendance.device.name,
        'device_ip': attendance.device.ip_address,
    }
    return data


def send_to_crm(attendance: ProcessedAttendance, retry_on_failure: bool = True) -> Tuple[bool, str]:
    """
    Send a single processed attendance record to the CRM.
    
    Args:
        attendance: ProcessedAttendance instance to sync
        retry_on_failure: Whether to retry on failure
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    if not settings.CRM_API_URL:
        logger.error("CRM_API_URL not configured in settings")
        return False, "CRM API URL not configured"
    
    if not settings.CRM_API_TOKEN:
        logger.error("CRM_API_TOKEN not configured in settings")
        return False, "CRM API token not configured"
    
    # Prepare data
    data = prepare_attendance_data(attendance)
    
    # Prepare headers
    headers = {
        'Authorization': f'Token {settings.CRM_API_TOKEN}',
        'Content-Type': 'application/json',
    }
    
    # Create session with retries
    session = get_session_with_retries() if retry_on_failure else requests.Session()
    
    try:
        logger.info(f"Sending attendance to CRM: User {attendance.user_id}, Date {attendance.date}")
        
        response = session.post(
            settings.CRM_API_URL,
            json=data,
            headers=headers,
            timeout=settings.CRM_REQUEST_TIMEOUT
        )
        
        # Check response status
        if response.status_code in [200, 201]:
            logger.info(f"Successfully synced attendance: User {attendance.user_id}, Date {attendance.date}")
            attendance.mark_synced()
            return True, "Successfully synced to CRM"
        else:
            error_msg = f"CRM API returned status {response.status_code}: {response.text}"
            logger.error(error_msg)
            attendance.increment_sync_attempts()
            return False, error_msg
    
    except requests.exceptions.Timeout:
        error_msg = f"Request timeout after {settings.CRM_REQUEST_TIMEOUT} seconds"
        logger.error(error_msg)
        attendance.increment_sync_attempts()
        return False, error_msg
    
    except requests.exceptions.ConnectionError as e:
        error_msg = f"Connection error: {str(e)}"
        logger.error(error_msg)
        attendance.increment_sync_attempts()
        return False, error_msg
    
    except requests.exceptions.RequestException as e:
        error_msg = f"Request error: {str(e)}"
        logger.error(error_msg)
        attendance.increment_sync_attempts()
        return False, error_msg
    
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        attendance.increment_sync_attempts()
        return False, error_msg
    
    finally:
        session.close()


def sync_batch(attendances: List[ProcessedAttendance], delay_between: float = 0.1) -> dict:
    """
    Sync a batch of processed attendance records to CRM.
    
    Args:
        attendances: List of ProcessedAttendance instances
        delay_between: Delay in seconds between requests (to avoid rate limiting)
    
    Returns:
        Dictionary with sync results
    """
    results = {
        'total': len(attendances),
        'successful': 0,
        'failed': 0,
        'errors': []
    }
    
    logger.info(f"Starting batch sync of {results['total']} attendance records")
    
    for attendance in attendances:
        success, message = send_to_crm(attendance)
        
        if success:
            results['successful'] += 1
        else:
            results['failed'] += 1
            results['errors'].append({
                'user_id': attendance.user_id,
                'date': str(attendance.date),
                'error': message
            })
        
        # Delay between requests
        if delay_between > 0:
            time.sleep(delay_between)
    
    logger.info(f"Batch sync complete: {results['successful']} successful, {results['failed']} failed")
    return results


def sync_unsynced_attendance(limit: int = None) -> dict:
    """
    Sync all unsynced processed attendance records to CRM.
    
    Args:
        limit: Maximum number of records to sync (uses CRM_SYNC_BATCH_SIZE if not provided)
    
    Returns:
        Dictionary with sync results
    """
    if limit is None:
        limit = settings.CRM_SYNC_BATCH_SIZE
    
    # Get unsynced records
    unsynced = ProcessedAttendance.objects.filter(
        synced_to_crm=False
    ).order_by('date', 'user_id')[:limit]
    
    if not unsynced.exists():
        logger.info("No unsynced attendance records found")
        return {
            'total': 0,
            'successful': 0,
            'failed': 0,
            'errors': []
        }
    
    return sync_batch(list(unsynced))


def sync_by_date_range(start_date: date, end_date: date = None, force_resync: bool = False) -> dict:
    """
    Sync attendance records for a specific date range.
    
    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive), defaults to today if not provided
        force_resync: If True, sync even already synced records
    
    Returns:
        Dictionary with sync results
    """
    if end_date is None:
        end_date = timezone.now().date()
    
    # Build query
    query = {'date__gte': start_date, 'date__lte': end_date}
    if not force_resync:
        query['synced_to_crm'] = False
    
    attendances = ProcessedAttendance.objects.filter(**query).order_by('date', 'user_id')
    
    logger.info(f"Syncing attendance from {start_date} to {end_date} "
                f"({'force resync' if force_resync else 'unsynced only'})")
    
    return sync_batch(list(attendances))


def sync_by_user(user_id: str, start_date: date = None, end_date: date = None, force_resync: bool = False) -> dict:
    """
    Sync attendance records for a specific user.
    
    Args:
        user_id: User/Employee ID
        start_date: Optional start date filter
        end_date: Optional end date filter
        force_resync: If True, sync even already synced records
    
    Returns:
        Dictionary with sync results
    """
    # Build query
    query = {'user_id': user_id}
    
    if start_date:
        query['date__gte'] = start_date
    if end_date:
        query['date__lte'] = end_date
    if not force_resync:
        query['synced_to_crm'] = False
    
    attendances = ProcessedAttendance.objects.filter(**query).order_by('date')
    
    logger.info(f"Syncing attendance for user {user_id} "
                f"({'force resync' if force_resync else 'unsynced only'})")
    
    return sync_batch(list(attendances))


def retry_failed_syncs(max_attempts: int = 3) -> dict:
    """
    Retry syncing records that previously failed.
    
    Args:
        max_attempts: Only retry records with fewer than this many attempts
    
    Returns:
        Dictionary with sync results
    """
    failed = ProcessedAttendance.objects.filter(
        synced_to_crm=False,
        sync_attempts__gt=0,
        sync_attempts__lt=max_attempts
    ).order_by('sync_attempts', 'date')
    
    logger.info(f"Retrying {failed.count()} failed sync attempts")
    
    return sync_batch(list(failed))


def test_crm_connection() -> Tuple[bool, str]:
    """
    Test connection to the CRM API.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    if not settings.CRM_API_URL:
        return False, "CRM API URL not configured"
    
    if not settings.CRM_API_TOKEN:
        return False, "CRM API token not configured"
    
    headers = {
        'Authorization': f'Token {settings.CRM_API_TOKEN}',
        'Content-Type': 'application/json',
    }
    
    try:
        # Try to ping the API (assuming it has a health check endpoint)
        # If not, this will just test the connection
        response = requests.get(
            settings.CRM_API_URL,
            headers=headers,
            timeout=settings.CRM_REQUEST_TIMEOUT
        )
        
        if response.status_code in [200, 201, 405]:  # 405 = Method not allowed (but connection works)
            return True, f"CRM API connection successful (status: {response.status_code})"
        else:
            return False, f"CRM API returned status {response.status_code}: {response.text}"
    
    except requests.exceptions.Timeout:
        return False, f"Request timeout after {settings.CRM_REQUEST_TIMEOUT} seconds"
    
    except requests.exceptions.ConnectionError as e:
        return False, f"Connection error: {str(e)}"
    
    except Exception as e:
        return False, f"Error: {str(e)}"


def get_sync_statistics() -> dict:
    """
    Get statistics about sync status.
    
    Returns:
        Dictionary with sync statistics
    """
    from django.db.models import Count, Q
    
    stats = ProcessedAttendance.objects.aggregate(
        total=Count('id'),
        synced=Count('id', filter=Q(synced_to_crm=True)),
        unsynced=Count('id', filter=Q(synced_to_crm=False)),
        failed=Count('id', filter=Q(synced_to_crm=False, sync_attempts__gte=3)),
    )
    
    stats['sync_percentage'] = (stats['synced'] / stats['total'] * 100) if stats['total'] > 0 else 0
    
    return stats
