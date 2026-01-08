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


def classify_attendance(clock_in: datetime, clock_out: datetime, work_start: time, work_end: time, overnight_shift: bool = False, device_timezone: str = 'UTC') -> Tuple[bool, bool, bool, str]:
    """
    Classify attendance punches into late arrival, early departure, or outlier categories.
    
    For night shift (20:00-05:00):
    - Late arrival: Punched in after acceptable window but still within evening hours
    - Early departure: Punched out before acceptable window but still within morning hours  
    - Outlier: Punches completely outside shift window (e.g., 7am-6pm) that can't be classified
    
    Args:
        clock_in: Clock-in datetime (in UTC)
        clock_out: Clock-out datetime (in UTC, can be None)
        work_start: Expected work start time (e.g., 20:00)
        work_end: Expected work end time (e.g., 05:00)
        overnight_shift: Whether the shift crosses midnight
        device_timezone: Timezone of the device (e.g., 'Africa/Nairobi')
    
    Returns:
        Tuple of (is_outlier: bool, is_late_arrival: bool, is_early_departure: bool, reason: str)
    """
    import pytz
    
    is_outlier = False
    is_late_arrival = False
    is_early_departure = False
    reasons = []
    
    # Convert UTC timestamps to device local time for comparison
    tz = pytz.timezone(device_timezone)
    
    # Get buffer settings - these define acceptable lateness/earliness
    late_clock_in_buffer = getattr(settings, 'LATE_CLOCK_IN_BUFFER_HOURS', 2)
    early_clock_out_buffer = getattr(settings, 'EARLY_CLOCK_OUT_BUFFER_HOURS', 2)
    
    # Get outlier detection thresholds - for completely anomalous punches
    outlier_early_in = getattr(settings, 'OUTLIER_EARLY_CLOCK_IN_HOURS', 2)
    outlier_late_out = getattr(settings, 'OUTLIER_LATE_CLOCK_OUT_HOURS', 2)
    
    if overnight_shift:
        # For overnight shifts (e.g., 20:00 to 05:00)
        
        # Check clock-in
        if clock_in:
            # Convert UTC timestamp to device local time
            clock_in_local = clock_in.astimezone(tz)
            clock_in_time = clock_in_local.time()
            
            # Latest acceptable clock-in = work_start + late_buffer (e.g., 20:00 + 2hr = 22:00)
            latest_clock_in_dt = datetime.combine(date.today(), work_start) + timedelta(hours=late_clock_in_buffer)
            latest_clock_in = latest_clock_in_dt.time()
            
            # Outlier threshold = work_start - outlier_early_in (e.g., 20:00 - 2hr = 18:00)
            outlier_early_threshold_dt = datetime.combine(date.today(), work_start) - timedelta(hours=outlier_early_in)
            outlier_early_threshold = outlier_early_threshold_dt.time()
            
            # For evening shift start (20:00):
            # - Normal: 18:00-20:00
            # - Late arrival: 20:01-22:00
            # - Outlier: Before 18:00 or daytime hours (e.g., 7am-6pm)
            
            if work_start.hour >= 12:  # Evening start
                # Check if late (after work_start but before latest acceptable)
                if clock_in_time > work_start and clock_in_time <= latest_clock_in:
                    is_late_arrival = True
                    reasons.append(f"Late arrival: clocked in at {clock_in_time.strftime('%H:%M')} (expected by {work_start.strftime('%H:%M')})")
                
                # Check if outlier (way too late or during daytime)
                elif clock_in_time > latest_clock_in:
                    # If it's in evening but past buffer, could still be late arrival
                    if clock_in_time.hour >= 18:  # Still evening-ish
                        is_late_arrival = True
                        reasons.append(f"Very late arrival: clocked in at {clock_in_time.strftime('%H:%M')} (expected by {work_start.strftime('%H:%M')})")
                    else:
                        # Daytime punch - unclassifiable outlier
                        is_outlier = True
                        reasons.append(f"Outlier clock-in: {clock_in_time.strftime('%H:%M')} (shift starts at {work_start.strftime('%H:%M')})")
                
                # Check if too early (before acceptable window)
                elif clock_in_time < outlier_early_threshold:
                    # If daytime, it's an outlier
                    if clock_in_time.hour < 12:
                        is_outlier = True
                        reasons.append(f"Outlier clock-in: {clock_in_time.strftime('%H:%M')} (shift starts at {work_start.strftime('%H:%M')})")
                    # If evening but before threshold (e.g., 17:00), it's an outlier
                    elif clock_in_time.hour < 18:
                        is_outlier = True
                        reasons.append(f"Clock-in too early: {clock_in_time.strftime('%H:%M')} (expected after {outlier_early_threshold.strftime('%H:%M')})")
                # Otherwise it's between outlier_early_threshold and work_start (18:00-20:00) = normal
        
        # Check clock-out
        if clock_out:
            # Convert UTC timestamp to device local time
            clock_out_local = clock_out.astimezone(tz)
            clock_out_time = clock_out_local.time()
            
            # Earliest acceptable clock-out = work_end - early_buffer (e.g., 05:00 - 2hr = 03:00)
            earliest_clock_out_dt = datetime.combine(date.today(), work_end) - timedelta(hours=early_clock_out_buffer)
            earliest_clock_out = earliest_clock_out_dt.time()
            
            # Outlier threshold = work_end + outlier_late_out (e.g., 05:00 + 2hr = 07:00)
            outlier_late_threshold_dt = datetime.combine(date.today(), work_end) + timedelta(hours=outlier_late_out)
            outlier_late_threshold = outlier_late_threshold_dt.time()
            
            # For morning shift end (05:00):
            # - Normal: 05:00-07:00
            # - Early departure: 03:00-04:59
            # - Outlier: Before 03:00 or afternoon hours
            
            if work_end.hour < 12:  # Morning end
                # Check if early (before work_end but after earliest acceptable)
                if clock_out_time < work_end and clock_out_time >= earliest_clock_out:
                    is_early_departure = True
                    reasons.append(f"Early departure: clocked out at {clock_out_time.strftime('%H:%M')} (expected after {work_end.strftime('%H:%M')})")
                
                # Check if outlier (way too early - before earliest threshold)
                elif clock_out_time < earliest_clock_out:
                    # If still in early morning hours, it's early departure
                    if clock_out_time.hour < 12:  # Still morning
                        is_early_departure = True
                        reasons.append(f"Very early departure: clocked out at {clock_out_time.strftime('%H:%M')} (expected after {work_end.strftime('%H:%M')})")
                    else:
                        # Afternoon/evening - unclassifiable outlier
                        is_outlier = True
                        reasons.append(f"Outlier clock-out: {clock_out_time.strftime('%H:%M')} (shift ends at {work_end.strftime('%H:%M')})")
                
                # Check if too late
                elif clock_out_time > outlier_late_threshold:
                    # If it's afternoon/evening, it's an outlier
                    if clock_out_time.hour >= 12:
                        is_outlier = True
                        reasons.append(f"Outlier clock-out: {clock_out_time.strftime('%H:%M')} (shift ends at {work_end.strftime('%H:%M')})")
    
    else:
        # Regular day shift logic (keep existing behavior for non-overnight shifts)
        # Get tolerance settings from Django settings
        early_clock_in_hours = getattr(settings, 'OUTLIER_EARLY_CLOCK_IN_HOURS', 2)
        late_clock_in_hours = getattr(settings, 'OUTLIER_LATE_CLOCK_IN_HOURS', 2)
        early_clock_out_hours = getattr(settings, 'OUTLIER_EARLY_CLOCK_OUT_HOURS', 2)
        late_clock_out_hours = getattr(settings, 'OUTLIER_LATE_CLOCK_OUT_HOURS', 3)
        
        if clock_in:
            # Convert UTC to device local time
            clock_in_local = clock_in.astimezone(tz)
            clock_in_time = clock_in_local.time()
            early_threshold = (datetime.combine(date.today(), work_start) - timedelta(hours=early_clock_in_hours)).time()
            late_threshold = (datetime.combine(date.today(), work_start) + timedelta(hours=late_clock_in_hours)).time()
            
            if clock_in_time < early_threshold:
                is_outlier = True
                reasons.append(f"Clock-in too early: {clock_in_time.strftime('%H:%M')} (expected after {early_threshold.strftime('%H:%M')})")
            elif clock_in_time > late_threshold:
                is_late_arrival = True
                reasons.append(f"Late arrival: {clock_in_time.strftime('%H:%M')} (expected before {late_threshold.strftime('%H:%M')})")
        
        if clock_out:
            # Convert UTC to device local time
            clock_out_local = clock_out.astimezone(tz)
            clock_out_time = clock_out_local.time()
            early_end_threshold = (datetime.combine(date.today(), work_end) - timedelta(hours=early_clock_out_hours)).time()
            late_end_threshold = (datetime.combine(date.today(), work_end) + timedelta(hours=late_clock_out_hours)).time()
            
            if clock_out_time < early_end_threshold:
                is_early_departure = True
                reasons.append(f"Early departure: {clock_out_time.strftime('%H:%M')} (expected after {early_end_threshold.strftime('%H:%M')})")
            elif clock_out_time > late_end_threshold:
                is_outlier = True
                reasons.append(f"Clock-out too late: {clock_out_time.strftime('%H:%M')} (expected before {late_end_threshold.strftime('%H:%M')})")
    
    reason_text = "; ".join(reasons) if reasons else ""
    
    return is_outlier, is_late_arrival, is_early_departure, reason_text


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
    buffer_hours = getattr(settings, 'OVERNIGHT_SHIFT_BUFFER_HOURS', 2)
    
    if overnight_shift:
        # For overnight shifts (e.g., 20:00 to 05:00)
        # We need to query from evening of attendance_date to morning of next day
        # Include early arrival buffer (e.g., 20:00 - 2hr = 18:00)
        
        outlier_early_in = getattr(settings, 'OUTLIER_EARLY_CLOCK_IN_HOURS', 2)
        
        # Get device timezone (or use first device's timezone if not specified)
        import pytz
        device_tz = device.timezone if device else Device.objects.first().timezone
        tz = pytz.timezone(device_tz)
        
        # Start: attendance_date at (work_start - outlier_early_in) in LOCAL time
        shift_start_local = datetime.combine(attendance_date, work_start) - timedelta(hours=outlier_early_in)
        shift_start = tz.localize(shift_start_local)
        
        # End: next day at work_end time + buffer in LOCAL time
        next_day = attendance_date + timedelta(days=1)
        shift_end_local = datetime.combine(next_day, work_end) + timedelta(hours=buffer_hours)
        shift_end = tz.localize(shift_end_local)
        
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
    
    # For overnight shifts, determine the correct shift date
    # Only morning punches (very early, before the shift window) belong to previous day's shift
    shift_date = attendance_date
    if overnight_shift:
        import pytz
        tz = pytz.timezone(device_obj.timezone)
        clock_in_local = clock_in.astimezone(tz)
        clock_in_time = clock_in_local.time()
        
        # Early morning punches (before the early buffer window) belong to previous day's shift
        # E.g., if work_start is 20:00 and buffer is 2hr, window starts at 18:00
        # So punches before 18:00 (like 05:00 morning) are from previous shift
        outlier_early_in = getattr(settings, 'OUTLIER_EARLY_CLOCK_IN_HOURS', 2)
        earliest_acceptable = (datetime.combine(date.today(), work_start) - timedelta(hours=outlier_early_in)).time()
        
        # If punch is in early morning (before noon) AND before the shift window start
        if clock_in_time.hour < 12 and clock_in_time < earliest_acceptable:
            shift_date = attendance_date - timedelta(days=1)
            logger.debug(f"Overnight shift: Morning punch at {clock_in_time} on {attendance_date} assigned to shift date {shift_date}")
        elif clock_in_time < earliest_acceptable and clock_in_time.hour >= 12:
            # Afternoon punch before window (e.g., 15:00 when window starts at 18:00)
            # This should stay on the same date - it's just early for THIS shift
            pass
    
    # Classify attendance (check for late/early/outlier)
    # Pass device timezone so comparison happens in local time, not UTC
    is_outlier_flag, is_late_flag, is_early_flag, outlier_reason = classify_attendance(
        clock_in, clock_out, work_start, work_end, overnight_shift, device_obj.timezone
    )
    
    # Create or update processed attendance
    processed, created = ProcessedAttendance.objects.update_or_create(
        device=device_obj,
        user_id=user_id,
        date=shift_date,
        defaults={
            'clock_in': clock_in,
            'clock_out': clock_out,
            'is_outlier': is_outlier_flag,
            'is_late_arrival': is_late_flag,
            'is_early_departure': is_early_flag,
            'outlier_reason': outlier_reason,
        }
    )
    
    action = "Created" if created else "Updated"
    logger.info(f"{action} processed attendance for user {user_id} on {shift_date}: "
                f"Clock-in: {clock_in.strftime('%H:%M:%S')}, "
                f"Clock-out: {clock_out.strftime('%H:%M:%S') if clock_out else 'N/A'}, "
                f"Late: {is_late_flag}, Early: {is_early_flag}, Outlier: {is_outlier_flag}")
    
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
