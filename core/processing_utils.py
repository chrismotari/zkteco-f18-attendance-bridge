"""
Attendance processing utilities.

This module provides functions to:
- Process raw attendance logs into clock-in/clock-out records
- Identify outliers based on work hours
- Deduplicate and normalize attendance data
- Handle edge cases in attendance processing
"""
import logging
from datetime import datetime, time, timedelta, date
from typing import List, Tuple, Optional
from django.conf import settings
from django.utils import timezone
from django.db.models import Q
from .models import RawAttendance, ProcessedAttendance, Device

logger = logging.getLogger('core')


def parse_work_time(time_str: str) -> time:
    """
    Parse time string in HH:MM format to time object.
    
    Args:
        time_str: Time string in HH:MM format
    
    Returns:
        time object
    """
    try:
        hour, minute = map(int, time_str.split(':'))
        return time(hour=hour, minute=minute)
    except Exception as e:
        logger.error(f"Error parsing time string '{time_str}': {str(e)}")
        return time(hour=9, minute=0)  # Default to 9:00 AM


def is_outlier(clock_in: datetime, clock_out: datetime, work_start: time, work_end: time, overnight_shift: bool = False) -> Tuple[bool, str]:
    """
    Check if attendance times are outside normal work hours (outliers).
    
    Args:
        clock_in: Clock-in datetime
        clock_out: Clock-out datetime (can be None)
        work_start: Expected work start time
        work_end: Expected work end time
        overnight_shift: Whether the shift crosses midnight
    
    Returns:
        Tuple of (is_outlier: bool, reason: str)
    """
    reasons = []
    
    # Get tolerance settings from Django settings
    early_clock_in_hours = getattr(settings, 'OUTLIER_EARLY_CLOCK_IN_HOURS', 2)
    late_clock_in_hours = getattr(settings, 'OUTLIER_LATE_CLOCK_IN_HOURS', 2)
    early_clock_out_hours = getattr(settings, 'OUTLIER_EARLY_CLOCK_OUT_HOURS', 2)
    late_clock_out_hours = getattr(settings, 'OUTLIER_LATE_CLOCK_OUT_HOURS', 3)
    
    # Check clock-in time
    if clock_in:
        clock_in_time = clock_in.time()
        
        if overnight_shift:
            # For overnight shifts, clock-in should be in the evening
            early_threshold_dt = datetime.combine(date.today(), work_start) - timedelta(hours=early_clock_in_hours)
            late_threshold_dt = datetime.combine(date.today(), work_start) + timedelta(hours=late_clock_in_hours)
            
            # Handle time wrapping around midnight
            early_threshold = early_threshold_dt.time()
            late_threshold = late_threshold_dt.time()
            
            # For overnight shifts starting in evening (e.g., 20:00)
            # Valid clock-in: 18:00 (20:00-2h) to 22:00 (20:00+2h)
            if work_start.hour >= 12:  # Evening start
                # If thresholds wrap around midnight (unlikely for clock-in)
                if early_threshold > late_threshold:
                    # Valid if >= early OR <= late
                    if not (clock_in_time >= early_threshold or clock_in_time <= late_threshold):
                        reasons.append(f"Clock-in outside shift window: {clock_in_time.strftime('%H:%M')} (expected {early_threshold.strftime('%H:%M')}-{late_threshold.strftime('%H:%M')})")
                else:
                    # Valid if between early and late (normal case)
                    if not (early_threshold <= clock_in_time <= late_threshold):
                        reasons.append(f"Clock-in outside shift window: {clock_in_time.strftime('%H:%M')} (expected {early_threshold.strftime('%H:%M')}-{late_threshold.strftime('%H:%M')})")
        else:
            # Regular day shift logic
            # Calculate valid clock-in window
            early_threshold = (datetime.combine(date.today(), work_start) - timedelta(hours=early_clock_in_hours)).time()
            late_threshold = (datetime.combine(date.today(), work_start) + timedelta(hours=late_clock_in_hours)).time()
            
            # Only mark as outlier if OUTSIDE the valid window
            if clock_in_time < early_threshold:
                reasons.append(f"Clock-in too early: {clock_in_time.strftime('%H:%M')} (expected after {early_threshold.strftime('%H:%M')})")
            elif clock_in_time > late_threshold:
                reasons.append(f"Clock-in too late: {clock_in_time.strftime('%H:%M')} (expected before {late_threshold.strftime('%H:%M')})")
    
    # Check clock-out time
    if clock_out:
        clock_out_time = clock_out.time()
        
        if overnight_shift:
            # For overnight shifts, clock-out should be in the morning
            early_end_threshold_dt = datetime.combine(date.today(), work_end) - timedelta(hours=early_clock_out_hours)
            late_end_threshold_dt = datetime.combine(date.today(), work_end) + timedelta(hours=late_clock_out_hours)
            
            early_end_threshold = early_end_threshold_dt.time()
            late_end_threshold = late_end_threshold_dt.time()
            
            # For overnight shifts ending in morning (e.g., 05:00)
            # Valid clock-out: 03:00 (05:00-2h) to 08:00 (05:00+3h)
            if work_end.hour < 12:  # Morning end
                # Valid if between thresholds (normal case for morning times)
                if not (early_end_threshold <= clock_out_time <= late_end_threshold):
                    reasons.append(f"Clock-out outside shift window: {clock_out_time.strftime('%H:%M')} (expected {early_end_threshold.strftime('%H:%M')}-{late_end_threshold.strftime('%H:%M')})")
        else:
            # Regular day shift logic
            # Calculate valid clock-out window
            early_end_threshold = (datetime.combine(date.today(), work_end) - timedelta(hours=early_clock_out_hours)).time()
            late_end_threshold = (datetime.combine(date.today(), work_end) + timedelta(hours=late_clock_out_hours)).time()
            
            # Only mark as outlier if OUTSIDE the valid window
            if clock_out_time < early_end_threshold:
                reasons.append(f"Clock-out too early: {clock_out_time.strftime('%H:%M')} (expected after {early_end_threshold.strftime('%H:%M')})")
            elif clock_out_time > late_end_threshold:
                reasons.append(f"Clock-out too late: {clock_out_time.strftime('%H:%M')} (expected before {late_end_threshold.strftime('%H:%M')})")
    
    is_outlier_flag = len(reasons) > 0
    reason_text = "; ".join(reasons) if reasons else ""
    
    return is_outlier_flag, reason_text


def process_attendance_for_date(user_id: str, attendance_date: date, device: Device = None) -> Optional[ProcessedAttendance]:
    """
    Process raw attendance records for a specific user and date.
    
    For overnight shifts, this groups punches from the evening of attendance_date
    through the morning of the next day.
    
    Identifies the earliest punch as clock-in and latest punch as clock-out.
    Flags outliers based on configured work hours.
    
    Args:
        user_id: User/Employee ID
        attendance_date: Date to process (the date the shift STARTS)
        device: Optional device filter
    
    Returns:
        ProcessedAttendance instance or None if no records found
    """
    # Get work hours from settings
    work_start = parse_work_time(settings.WORK_START_TIME)
    work_end = parse_work_time(settings.WORK_END_TIME)
    overnight_shift = getattr(settings, 'OVERNIGHT_SHIFT', False)
    
    if overnight_shift:
        # For overnight shifts (e.g., 20:00 to 05:00)
        # We need to query from evening of attendance_date to morning of next day
        
        # Start: attendance_date at work_start time (e.g., 20:00)
        shift_start = datetime.combine(attendance_date, work_start)
        
        # End: next day at work_end time + buffer (e.g., next day 08:00 for 05:00 end time)
        next_day = attendance_date + timedelta(days=1)
        shift_end_time = (datetime.combine(next_day, work_end) + timedelta(hours=3)).time()
        shift_end = datetime.combine(next_day, shift_end_time)
        
        # Make timezone aware if needed
        if settings.USE_TZ:
            shift_start = timezone.make_aware(shift_start)
            shift_end = timezone.make_aware(shift_end)
        
        # Query for punches within the shift window
        query = Q(
            user_id=user_id,
            timestamp__gte=shift_start,
            timestamp__lte=shift_end
        )
    else:
        # For regular day shifts, query just the specific date
        query = Q(user_id=user_id, timestamp__date=attendance_date)
    
    if device:
        query &= Q(device=device)
    
    raw_records = RawAttendance.objects.filter(query).order_by('timestamp')
    
    if not raw_records.exists():
        logger.debug(f"No raw attendance records found for user {user_id} on {attendance_date}")
        return None
    
    # Get earliest and latest punches
    first_punch = raw_records.first()
    last_punch = raw_records.last()
    
    clock_in = first_punch.timestamp
    clock_out = last_punch.timestamp if first_punch.id != last_punch.id else None
    
    # Determine device (use first record's device)
    device_obj = device or first_punch.device
    
    # Check for outliers
    outlier_flag, outlier_reason = is_outlier(clock_in, clock_out, work_start, work_end, overnight_shift)
    
    # Create or update processed attendance
    processed, created = ProcessedAttendance.objects.update_or_create(
        device=device_obj,
        user_id=user_id,
        date=attendance_date,
        defaults={
            'clock_in': clock_in,
            'clock_out': clock_out,
            'is_outlier': outlier_flag,
            'outlier_reason': outlier_reason,
        }
    )
    
    action = "Created" if created else "Updated"
    logger.info(f"{action} processed attendance for user {user_id} on {attendance_date}: "
                f"Clock-in: {clock_in.strftime('%H:%M:%S')}, "
                f"Clock-out: {clock_out.strftime('%H:%M:%S') if clock_out else 'N/A'}, "
                f"Outlier: {outlier_flag}")
    
    return processed


def process_all_unprocessed_attendance() -> dict:
    """
    Process all raw attendance records that haven't been processed yet.
    
    For overnight shifts, groups punches by their shift start date.
    
    Returns:
        Dictionary with processing results
    """
    overnight_shift = getattr(settings, 'OVERNIGHT_SHIFT', False)
    work_start = parse_work_time(settings.WORK_START_TIME)
    
    results = {
        'total_records': 0,
        'processed': 0,
        'failed': 0,
        'outliers': 0
    }
    
    logger.info("Starting processing of all unprocessed attendance records")
    
    if overnight_shift:
        # For overnight shifts, we need to group punches by shift start date
        # Get all raw records and group them by user and shift
        raw_records = RawAttendance.objects.all().order_by('user_id', 'timestamp')
        
        # Group by user_id
        from itertools import groupby
        
        for user_id, user_records in groupby(raw_records, key=lambda x: x.user_id):
            user_records_list = list(user_records)
            processed_shifts = set()
            
            for record in user_records_list:
                # Determine which shift this punch belongs to
                punch_time = record.timestamp.time()
                punch_date = record.timestamp.date()
                
                # If punch is after work_start (evening), it's the start of a shift on that date
                # If punch is before work_start (morning), it belongs to previous day's shift
                if punch_time >= work_start:
                    shift_date = punch_date
                else:
                    shift_date = punch_date - timedelta(days=1)
                
                # Create unique key for this shift
                shift_key = (user_id, shift_date, record.device_id)
                
                if shift_key not in processed_shifts:
                    try:
                        device = Device.objects.get(id=record.device_id)
                        processed = process_attendance_for_date(user_id, shift_date, device)
                        
                        if processed:
                            results['processed'] += 1
                            if processed.is_outlier:
                                results['outliers'] += 1
                        
                        results['total_records'] += 1
                        processed_shifts.add(shift_key)
                    except Exception as e:
                        results['failed'] += 1
                        logger.error(f"Error processing attendance for user {user_id} on {shift_date}: {str(e)}")
    else:
        # For regular shifts, use calendar date grouping
        raw_records = RawAttendance.objects.values('user_id', 'timestamp__date', 'device').distinct()
        
        for record in raw_records:
            user_id = record['user_id']
            attendance_date = record['timestamp__date']
            device_id = record['device']
            
            try:
                device = Device.objects.get(id=device_id)
                processed = process_attendance_for_date(user_id, attendance_date, device)
                
                if processed:
                    results['processed'] += 1
                    if processed.is_outlier:
                        results['outliers'] += 1
                
                results['total_records'] += 1
            except Exception as e:
                results['failed'] += 1
                logger.error(f"Error processing attendance for user {user_id} on {attendance_date}: {str(e)}")
    
    logger.info(f"Processing complete: {results['processed']} processed, "
                f"{results['outliers']} outliers, {results['failed']} failed")
    
    return results


def process_attendance_for_date_range(start_date: date, end_date: date = None, device: Device = None) -> dict:
    """
    Process attendance for a date range.
    
    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive), defaults to today if not provided
        device: Optional device filter
    
    Returns:
        Dictionary with processing results
    """
    if end_date is None:
        end_date = timezone.now().date()
    
    results = {
        'start_date': start_date,
        'end_date': end_date,
        'total_days': (end_date - start_date).days + 1,
        'processed': 0,
        'failed': 0,
        'outliers': 0
    }
    
    logger.info(f"Processing attendance from {start_date} to {end_date}")
    
    # Query raw attendance for date range
    query = Q(timestamp__date__gte=start_date, timestamp__date__lte=end_date)
    if device:
        query &= Q(device=device)
    
    raw_records = RawAttendance.objects.filter(query).values('user_id', 'timestamp__date', 'device').distinct()
    
    for record in raw_records:
        user_id = record['user_id']
        attendance_date = record['timestamp__date']
        device_id = record['device']
        
        try:
            device_obj = Device.objects.get(id=device_id)
            processed = process_attendance_for_date(user_id, attendance_date, device_obj)
            
            if processed:
                results['processed'] += 1
                if processed.is_outlier:
                    results['outliers'] += 1
        except Exception as e:
            results['failed'] += 1
            logger.error(f"Error processing attendance for user {user_id} on {attendance_date}: {str(e)}")
    
    logger.info(f"Date range processing complete: {results['processed']} processed, "
                f"{results['outliers']} outliers, {results['failed']} failed")
    
    return results


def process_all_attendance_for_date(target_date: date, device_id: int = None) -> int:
    """
    Process all raw attendance records for a specific date.
    
    Args:
        target_date: Date to process attendance for
        device_id: Optional device ID to filter by
    
    Returns:
        Number of records processed
    """
    logger.info(f"Processing attendance for specific date: {target_date}")
    
    # Get all raw attendance for this date
    raw_records = RawAttendance.objects.filter(
        timestamp__date=target_date
    )
    
    # Apply device filter if specified
    if device_id:
        raw_records = raw_records.filter(device_id=device_id)
    
    raw_records = raw_records.select_related('device').order_by('timestamp')
    
    if not raw_records.exists():
        logger.info(f"No raw attendance records found for {target_date}")
        return 0
    
    # Group by device and user_id
    from itertools import groupby
    
    processed_count = 0
    
    # Group by device first
    for device_id_key, device_records in groupby(raw_records, key=lambda r: r.device_id):
        device_records_list = list(device_records)
        device = device_records_list[0].device
        
        # Group by user_id within device
        for user_id, user_records in groupby(device_records_list, key=lambda r: r.user_id):
            user_records_list = list(user_records)
            
            if not user_records_list:
                continue
            
            # Get first and last punch times
            first_punch = user_records_list[0]
            last_punch = user_records_list[-1]
            
            clock_in = first_punch.timestamp
            clock_out = last_punch.timestamp if len(user_records_list) > 1 else None
            
            # Check for outliers
            work_start = parse_work_time(settings.WORK_START_TIME)
            work_end = parse_work_time(settings.WORK_END_TIME)
            overnight_shift = getattr(settings, 'OVERNIGHT_SHIFT', False)
            
            is_outlier_flag, outlier_reason = is_outlier(
                clock_in, clock_out, work_start, work_end, overnight_shift
            )
            
            # Create or update processed record
            ProcessedAttendance.objects.update_or_create(
                device=device,
                user_id=user_id,
                date=target_date,
                defaults={
                    'clock_in': clock_in,
                    'clock_out': clock_out,
                    'is_outlier': is_outlier_flag,
                    'outlier_reason': outlier_reason,
                }
            )
            processed_count += 1
            logger.debug(f"Processed attendance for user {user_id} on {target_date}")
    
    logger.info(f"Processed {processed_count} attendance records for {target_date}")
    return processed_count


def deduplicate_records() -> dict:
    """
    Identify and handle duplicate processed attendance records.
    
    Returns:
        Dictionary with deduplication results
    """
    from django.db.models import Count
    
    # Find duplicates based on user_id, date, and device
    duplicates = (ProcessedAttendance.objects
                  .values('user_id', 'date', 'device')
                  .annotate(count=Count('id'))
                  .filter(count__gt=1))
    
    results = {
        'duplicate_groups': duplicates.count(),
        'records_removed': 0
    }
    
    logger.info(f"Found {results['duplicate_groups']} duplicate groups")
    
    for dup in duplicates:
        # Get all records in this duplicate group
        records = ProcessedAttendance.objects.filter(
            user_id=dup['user_id'],
            date=dup['date'],
            device_id=dup['device']
        ).order_by('-updated_at')
        
        # Keep the most recently updated record, delete others
        records_to_delete = records[1:]
        count = records_to_delete.count()
        records_to_delete.delete()
        
        results['records_removed'] += count
        logger.info(f"Removed {count} duplicate records for user {dup['user_id']} on {dup['date']}")
    
    logger.info(f"Deduplication complete: removed {results['records_removed']} duplicate records")
    return results


def normalize_attendance(user_id: str, attendance_date: date) -> Optional[ProcessedAttendance]:
    """
    Normalize and reprocess attendance for a specific user and date.
    This can be used to fix incorrectly processed records.
    
    Args:
        user_id: User/Employee ID
        attendance_date: Date to normalize
    
    Returns:
        ProcessedAttendance instance or None
    """
    logger.info(f"Normalizing attendance for user {user_id} on {attendance_date}")
    
    # Delete existing processed record
    ProcessedAttendance.objects.filter(user_id=user_id, date=attendance_date).delete()
    
    # Reprocess from raw data
    return process_attendance_for_date(user_id, attendance_date)


def get_unsynced_attendance(limit: int = None) -> List[ProcessedAttendance]:
    """
    Get processed attendance records that haven't been synced to CRM.
    
    Args:
        limit: Maximum number of records to return
    
    Returns:
        List of ProcessedAttendance instances
    """
    queryset = ProcessedAttendance.objects.filter(synced_to_crm=False).order_by('date', 'user_id')
    
    if limit:
        queryset = queryset[:limit]
    
    return list(queryset)


def get_failed_sync_attendance(max_attempts: int = 3) -> List[ProcessedAttendance]:
    """
    Get processed attendance records that failed to sync multiple times.
    
    Args:
        max_attempts: Maximum number of failed attempts before considering it failed
    
    Returns:
        List of ProcessedAttendance instances
    """
    queryset = ProcessedAttendance.objects.filter(
        synced_to_crm=False,
        sync_attempts__gte=max_attempts
    ).order_by('-sync_attempts', 'date')
    
    return list(queryset)
