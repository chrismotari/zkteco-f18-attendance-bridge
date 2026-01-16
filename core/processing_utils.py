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


def classify_attendance(clock_in: datetime, clock_out: datetime, work_start: time, work_end: time, overnight_shift: bool = False, device_timezone: str = 'UTC') -> Tuple[bool, bool, bool, bool, str]:
    """
    Classify in-window attendance punches into categories.
    
    NOTE: This function now ONLY classifies IN-WINDOW punches. Outliers (out-of-window punches)
    are already filtered and stored in OutlierPunch table before this function is called.
    
    Categories checked:
    - Incomplete: Missing clock-in OR clock-out
    - Late arrival: Punched in after work_start (but within acceptable window)
    - Early departure: Punched out before work_end (but within acceptable window)
    
    Args:
        clock_in: Clock-in datetime (in UTC, can be None) - Already filtered to be in-window
        clock_out: Clock-out datetime (in UTC, can be None) - Already filtered to be in-window
        work_start: Expected work start time (e.g., 20:00)
        work_end: Expected work end time (e.g., 05:00)
        overnight_shift: Whether the shift crosses midnight
        device_timezone: Timezone of the device (e.g., 'Africa/Nairobi')
    
    Returns:
        Tuple of (is_outlier: bool, is_late_arrival: bool, is_early_departure: bool, is_incomplete: bool, reason: str)
        Note: is_outlier will always be False now since outliers are pre-filtered
    """
    import pytz
    
    is_outlier = False  # Always False - outliers are now in separate table
    is_late_arrival = False
    is_early_departure = False
    is_incomplete = False
    reasons = []
    
    # Check for incomplete attendance first
    if not clock_in or not clock_out:
        is_incomplete = True
        if not clock_in and not clock_out:
            reasons.append("Missing both clock-in and clock-out")
        elif not clock_in:
            reasons.append("Missing clock-in")
        else:
            reasons.append("Missing clock-out")
        
        # Return early - incomplete is a separate category from late/early
        reason_text = "; ".join(reasons)
        return is_outlier, is_late_arrival, is_early_departure, is_incomplete, reason_text
    
    # Convert UTC timestamps to device local time for comparison
    tz = pytz.timezone(device_timezone)
    
    # Check clock-in timing - is it after the expected start time?
    if clock_in:
        clock_in_local = clock_in.astimezone(tz)
        clock_in_time = clock_in_local.time()
        
        # Late if punched in after work_start
        if clock_in_time > work_start:
            is_late_arrival = True
            minutes_late = (datetime.combine(date.today(), clock_in_time) - 
                          datetime.combine(date.today(), work_start)).total_seconds() / 60
            reasons.append(f"Late arrival: clocked in at {clock_in_time.strftime('%H:%M')} ({int(minutes_late)} min late)")
    
    # Check clock-out timing - is it before the expected end time?
    if clock_out:
        clock_out_local = clock_out.astimezone(tz)
        clock_out_time = clock_out_local.time()
        
        # For overnight shifts, handle time comparison differently
        if overnight_shift and work_end.hour < 12:
            # work_end is in the morning (e.g., 05:00)
            # Early if punched out before work_end in the morning hours
            if clock_out_time.hour < 12 and clock_out_time < work_end:
                is_early_departure = True
                minutes_early = (datetime.combine(date.today(), work_end) - 
                               datetime.combine(date.today(), clock_out_time)).total_seconds() / 60
                reasons.append(f"Left early: clocked out at {clock_out_time.strftime('%H:%M')} ({int(minutes_early)} min early)")
        else:
            # Regular day shift or non-overnight
            if clock_out_time < work_end:
                is_early_departure = True
                minutes_early = (datetime.combine(date.today(), work_end) - 
                               datetime.combine(date.today(), clock_out_time)).total_seconds() / 60
                reasons.append(f"Left early: clocked out at {clock_out_time.strftime('%H:%M')} ({int(minutes_early)} min early)")
    
    reason_text = "; ".join(reasons) if reasons else ""
    
    return is_outlier, is_late_arrival, is_early_departure, is_incomplete, reason_text


def is_punch_in_shift_window(punch_datetime: datetime, shift_date: date, work_start: time, work_end: time, 
                               overnight_shift: bool, device_timezone: str, buffer_hours: int = 2) -> bool:
    """
    Determine if a punch falls within the acceptable shift window.
    
    For overnight shifts (e.g., 20:00-05:00), the window is:
    - Start: shift_date at (work_start - buffer_hours) 
    - End: next_day at (work_end + buffer_hours)
    
    For day shifts, the window is:
    - Start: shift_date at (work_start - buffer_hours)
    - End: shift_date at (work_end + buffer_hours)
    
    Args:
        punch_datetime: The punch timestamp in UTC
        shift_date: The shift date (when shift starts)
        work_start: Expected shift start time (e.g., 20:00)
        work_end: Expected shift end time (e.g., 05:00)
        overnight_shift: Whether the shift crosses midnight
        device_timezone: Timezone of the device
        buffer_hours: Hours of buffer before/after shift times
    
    Returns:
        True if punch is within shift window, False otherwise
    """
    import pytz
    
    tz = pytz.timezone(device_timezone)
    
    # Calculate shift window start and end in local time
    window_start_local = datetime.combine(shift_date, work_start) - timedelta(hours=buffer_hours)
    
    if overnight_shift:
        # Shift ends next day
        next_day = shift_date + timedelta(days=1)
        window_end_local = datetime.combine(next_day, work_end) + timedelta(hours=buffer_hours)
    else:
        # Shift ends same day
        window_end_local = datetime.combine(shift_date, work_end) + timedelta(hours=buffer_hours)
    
    # Localize to device timezone
    window_start = tz.localize(window_start_local)
    window_end = tz.localize(window_end_local)
    
    return window_start <= punch_datetime <= window_end


def determine_outlier_reason(punch_datetime: datetime, shift_date: date, work_start: time, work_end: time,
                              overnight_shift: bool, device_timezone: str) -> str:
    """
    Determine why a punch is considered an outlier (outside shift window).
    
    Args:
        punch_datetime: The punch timestamp in UTC
        shift_date: The shift date
        work_start: Expected shift start time
        work_end: Expected shift end time
        overnight_shift: Whether the shift crosses midnight
        device_timezone: Timezone of the device
    
    Returns:
        Human-readable reason string
    """
    import pytz
    
    tz = pytz.timezone(device_timezone)
    punch_local = punch_datetime.astimezone(tz)
    punch_time = punch_local.time()
    
    buffer_hours = getattr(settings, 'OVERNIGHT_SHIFT_BUFFER_HOURS', 2)
    
    if overnight_shift:
        # Calculate acceptable window
        earliest_acceptable = (datetime.combine(date.today(), work_start) - timedelta(hours=buffer_hours)).time()
        next_day_latest = (datetime.combine(date.today(), work_end) + timedelta(hours=buffer_hours)).time()
        
        # Check if it's way before shift start
        if punch_time < earliest_acceptable and punch_time.hour >= 12:
            hours_early = (datetime.combine(date.today(), earliest_acceptable) - 
                          datetime.combine(date.today(), punch_time)).total_seconds() / 3600
            return f"Punch at {punch_time.strftime('%H:%M')} is {hours_early:.1f} hours before shift window starts"
        
        # Check if it's after morning window ends
        elif punch_time > next_day_latest and punch_time.hour < 12:
            hours_late = (datetime.combine(date.today(), punch_time) - 
                         datetime.combine(date.today(), next_day_latest)).total_seconds() / 3600
            return f"Punch at {punch_time.strftime('%H:%M')} is {hours_late:.1f} hours after shift window ends"
        
        # Punch during the day when shift is overnight
        elif 6 <= punch_time.hour <= 17:
            return f"Punch at {punch_time.strftime('%H:%M')} during day hours for overnight shift ({work_start.strftime('%H:%M')}-{work_end.strftime('%H:%M')})"
        
        else:
            return f"Punch at {punch_time.strftime('%H:%M')} outside shift window"
    else:
        # Day shift
        earliest_acceptable = (datetime.combine(date.today(), work_start) - timedelta(hours=buffer_hours)).time()
        latest_acceptable = (datetime.combine(date.today(), work_end) + timedelta(hours=buffer_hours)).time()
        
        if punch_time < earliest_acceptable:
            hours_early = (datetime.combine(date.today(), earliest_acceptable) - 
                          datetime.combine(date.today(), punch_time)).total_seconds() / 3600
            return f"Punch at {punch_time.strftime('%H:%M')} is {hours_early:.1f} hours before shift starts"
        else:
            hours_late = (datetime.combine(date.today(), punch_time) - 
                         datetime.combine(date.today(), latest_acceptable)).total_seconds() / 3600
            return f"Punch at {punch_time.strftime('%H:%M')} is {hours_late:.1f} hours after shift ends"


def process_attendance_for_date(user_id: str, attendance_date: date, device: Device = None) -> Optional[ProcessedAttendance]:
    """
    Process raw attendance records for a specific user and date using NEW ARCHITECTURE.
    
    NEW APPROACH:
    1. Get all punches for the user on attendance_date (with shift window expansion for overnight)
    2. Filter punches: IN-WINDOW vs OUT-OF-WINDOW
    3. Out-of-window punches → Create OutlierPunch records
    4. In-window punches → Create ProcessedAttendance with earliest/latest/count
    5. Classify in-window punches for late/early/incomplete flags
    
    For overnight shifts, groups punches from evening of attendance_date
    through the morning of the next day.
    
    Args:
        user_id: User/Employee ID
        attendance_date: Date to process (the date the shift STARTS)
        device: Optional device filter
    
    Returns:
        ProcessedAttendance instance or None if no records found
    """
    from .models import OutlierPunch
    import pytz
    
    # Get work hours from settings
    work_start = parse_work_time(settings.WORK_START_TIME)
    work_end = parse_work_time(settings.WORK_END_TIME)
    overnight_shift = getattr(settings, 'OVERNIGHT_SHIFT', False)
    buffer_hours = getattr(settings, 'OVERNIGHT_SHIFT_BUFFER_HOURS', 2)
    
    # Get device timezone
    if device:
        device_tz = device.timezone
        device_obj = device
    else:
        first_device = Device.objects.first()
        device_tz = first_device.timezone if first_device else settings.TIME_ZONE
        device_obj = first_device
    
    if not device_obj:
        logger.error("No device available for processing attendance")
        return None
    
    tz = pytz.timezone(device_tz)
    
    # Calculate the query window (wider than shift window to catch all potential punches)
    if overnight_shift:
        # Query from afternoon of attendance_date to late morning next day
        outlier_early_in = getattr(settings, 'OUTLIER_EARLY_CLOCK_IN_HOURS', 2)
        query_start_local = datetime.combine(attendance_date, work_start) - timedelta(hours=outlier_early_in + 2)
        query_start = tz.localize(query_start_local)
        
        next_day = attendance_date + timedelta(days=1)
        query_end_local = datetime.combine(next_day, work_end) + timedelta(hours=buffer_hours + 2)
        query_end = tz.localize(query_end_local)
    else:
        # For day shifts, query the full day with buffers
        query_start_local = datetime.combine(attendance_date, work_start) - timedelta(hours=buffer_hours + 2)
        query_start = tz.localize(query_start_local)
        
        query_end_local = datetime.combine(attendance_date, work_end) + timedelta(hours=buffer_hours + 2)
        query_end = tz.localize(query_end_local)
    
    # Query for all punches in the window
    query = Q(
        user_id=user_id,
        timestamp__gte=query_start,
        timestamp__lte=query_end
    )
    
    if device:
        query &= Q(device=device)
    
    all_punches = list(RawAttendance.objects.filter(query).order_by('timestamp'))
    
    if not all_punches:
        logger.debug(f"No raw attendance records found for user {user_id} on {attendance_date}")
        return None
    
    # STEP 2: Filter punches into IN-WINDOW and OUT-OF-WINDOW
    in_window_punches = []
    out_of_window_punches = []
    
    for punch in all_punches:
        if is_punch_in_shift_window(punch.timestamp, attendance_date, work_start, work_end, 
                                      overnight_shift, device_tz, buffer_hours):
            in_window_punches.append(punch)
        else:
            out_of_window_punches.append(punch)
    
    # STEP 3: Create OutlierPunch records for out-of-window punches
    for punch in out_of_window_punches:
        reason = determine_outlier_reason(punch.timestamp, attendance_date, work_start, work_end,
                                          overnight_shift, device_tz)
        
        OutlierPunch.objects.update_or_create(
            device=punch.device,
            user_id=user_id,
            punch_datetime=punch.timestamp,
            defaults={
                'reason': reason,
                'associated_shift_date': attendance_date,
                'reviewed': False,
            }
        )
        logger.info(f"Created outlier punch for user {user_id}: {punch.timestamp} - {reason}")
    
    # If no in-window punches, we still record the shift but mark as incomplete
    if not in_window_punches:
        logger.warning(f"No in-window punches for user {user_id} on {attendance_date}, "
                      f"but {len(out_of_window_punches)} outlier punches recorded")
        
        # Create a ProcessedAttendance record marking it as completely missing
        processed, created = ProcessedAttendance.objects.update_or_create(
            device=device_obj,
            user_id=user_id,
            shift_date=attendance_date,
            defaults={
                'shift_start_time': work_start,
                'shift_end_time': work_end,
                'earliest_punch': None,
                'latest_punch': None,
                'punch_count': 0,
                'is_incomplete': True,
                'is_late_arrival': False,
                'is_early_departure': False,
                'notes': f"No punches within shift window. {len(out_of_window_punches)} outlier punch(es) recorded separately.",
                # Legacy fields
                'date': attendance_date,
                'clock_in': None,
                'clock_out': None,
                'is_outlier': False,  # Outliers now separate
                'outlier_reason': '',
            }
        )
        return processed
    
    # STEP 4: Create ProcessedAttendance from in-window punches
    earliest_punch = in_window_punches[0]
    latest_punch = in_window_punches[-1]
    punch_count = len(in_window_punches)
    
    clock_in = earliest_punch.timestamp
    clock_out = latest_punch.timestamp if len(in_window_punches) > 1 else None
    
    # STEP 5: Classify in-window punches for late/early/incomplete
    _, is_late_flag, is_early_flag, is_incomplete_flag, classification_reason = classify_attendance(
        clock_in, clock_out, work_start, work_end, overnight_shift, device_tz
    )
    
    # Build notes
    notes_parts = []
    if classification_reason:
        notes_parts.append(classification_reason)
    if out_of_window_punches:
        notes_parts.append(f"{len(out_of_window_punches)} outlier punch(es) recorded separately")
    notes = "; ".join(notes_parts)
    
    # Create or update processed attendance
    processed, created = ProcessedAttendance.objects.update_or_create(
        device=device_obj,
        user_id=user_id,
        shift_date=attendance_date,
        defaults={
            'shift_start_time': work_start,
            'shift_end_time': work_end,
            'earliest_punch': clock_in,
            'latest_punch': clock_out,
            'punch_count': punch_count,
            'is_late_arrival': is_late_flag,
            'is_early_departure': is_early_flag,
            'is_incomplete': is_incomplete_flag,
            'notes': notes,
            # Legacy fields for backward compatibility
            'date': attendance_date,
            'clock_in': clock_in,
            'clock_out': clock_out,
            'is_outlier': False,  # Outliers now in separate table
            'outlier_reason': '',
        }
    )
    
    action = "Created" if created else "Updated"
    logger.info(f"{action} processed attendance for user {user_id} on {attendance_date}: "
                f"In-window punches: {punch_count}, Earliest: {clock_in.strftime('%H:%M:%S')}, "
                f"Latest: {clock_out.strftime('%H:%M:%S') if clock_out else 'N/A'}, "
                f"Incomplete: {is_incomplete_flag}, Late: {is_late_flag}, Early: {is_early_flag}, "
                f"Outliers: {len(out_of_window_punches)}")
    
    return processed


def process_all_unprocessed_attendance() -> dict:
    """
    Process all raw attendance records that haven't been processed yet.
    
    For overnight shifts, groups punches by their shift start date using
    efficient database queries instead of loading all records into memory.
    
    Returns:
        Dictionary with processing results
    """
    import pytz
    from django.db.models.functions import TruncDate
    
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
        # For overnight shifts, use database aggregation to get unique combinations
        # This is much more efficient than loading all records into memory
        
        # Get all unique user/device/date combinations from raw attendance
        # We'll use the date portion of timestamp to identify potential shifts
        unique_combinations = (RawAttendance.objects
                              .values('user_id', 'device_id', 'timestamp__date')
                              .distinct()
                              .order_by('user_id', 'device_id', 'timestamp__date'))
        
        logger.info(f"Found {unique_combinations.count()} unique user/device/date combinations to process")
        
        # Track processed shifts to avoid duplicates when a shift spans two dates
        processed_shifts = set()
        
        for combo in unique_combinations:
            user_id = combo['user_id']
            device_id = combo['device_id']
            punch_date = combo['timestamp__date']
            
            try:
                # Get device object (cache this in production)
                device = Device.objects.get(id=device_id)
                
                # For overnight shifts, we need to determine the shift start date
                # Check if there are any punches on this date that are evening punches (>= work_start)
                evening_punches = RawAttendance.objects.filter(
                    user_id=user_id,
                    device_id=device_id,
                    timestamp__date=punch_date
                ).select_related('device')
                
                # Determine shift dates to process for this combination
                shift_dates = set()
                
                for punch in evening_punches:
                    # Convert to device local time for comparison
                    tz = pytz.timezone(device.timezone)
                    punch_local = punch.timestamp.astimezone(tz)
                    punch_time = punch_local.time()
                    
                    # If punch is after work_start (evening), it's the start of a shift on that date
                    # If punch is before work_start (morning), it belongs to previous day's shift
                    if punch_time >= work_start:
                        shift_date = punch_date
                    else:
                        shift_date = punch_date - timedelta(days=1)
                    
                    shift_dates.add(shift_date)
                
                # Process each unique shift date
                for shift_date in shift_dates:
                    shift_key = (user_id, device_id, shift_date)
                    
                    if shift_key not in processed_shifts:
                        processed = process_attendance_for_date(user_id, shift_date, device)
                        
                        if processed:
                            results['processed'] += 1
                            if processed.is_outlier:
                                results['outliers'] += 1
                        
                        results['total_records'] += 1
                        processed_shifts.add(shift_key)
                        
            except Device.DoesNotExist:
                results['failed'] += 1
                logger.error(f"Device {device_id} not found for user {user_id}")
            except Exception as e:
                results['failed'] += 1
                logger.error(f"Error processing attendance for user {user_id} on {punch_date}: {str(e)}")
    else:
        # For regular shifts, use calendar date grouping with database aggregation
        # This avoids loading all records into memory
        unique_combinations = (RawAttendance.objects
                              .values('user_id', 'device_id', 'timestamp__date')
                              .distinct()
                              .order_by('user_id', 'device_id', 'timestamp__date'))
        
        logger.info(f"Found {unique_combinations.count()} unique user/device/date combinations to process")
        
        for combo in unique_combinations:
            user_id = combo['user_id']
            attendance_date = combo['timestamp__date']
            device_id = combo['device_id']
            
            try:
                device = Device.objects.get(id=device_id)
                processed = process_attendance_for_date(user_id, attendance_date, device)
                
                if processed:
                    results['processed'] += 1
                    if processed.is_outlier:
                        results['outliers'] += 1
                
                results['total_records'] += 1
            except Device.DoesNotExist:
                results['failed'] += 1
                logger.error(f"Device {device_id} not found for user {user_id}")
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
    
    Uses process_attendance_for_date() for each user to ensure consistency
    with recalculate and other processing paths.
    
    Args:
        target_date: Date to process attendance for
        device_id: Optional device ID to filter by
    
    Returns:
        Number of records processed
    """
    logger.info(f"Processing attendance for specific date: {target_date}")
    
    # Get all unique user_id/device combinations for this date
    query_filter = {'timestamp__date': target_date}
    if device_id:
        query_filter['device_id'] = device_id
    
    unique_combinations = (RawAttendance.objects
                          .filter(**query_filter)
                          .values('user_id', 'device_id')
                          .distinct())
    
    if not unique_combinations.exists():
        logger.info(f"No raw attendance records found for {target_date}")
        return 0
    
    processed_count = 0
    
    # Process each unique user/device combination using the same logic
    # as recalculate and background tasks
    for combo in unique_combinations:
        user_id = combo['user_id']
        device_id_val = combo['device_id']
        
        try:
            device = Device.objects.get(id=device_id_val)
            # Use the central processing function to ensure consistency
            processed = process_attendance_for_date(user_id, target_date, device)
            
            if processed:
                processed_count += 1
                logger.debug(f"Processed attendance for user {user_id} on {target_date}")
                
        except Device.DoesNotExist:
            logger.error(f"Device {device_id_val} not found for user {user_id}")
        except Exception as e:
            logger.error(f"Error processing attendance for user {user_id} on {target_date}: {str(e)}")
    
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
