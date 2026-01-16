from django import template
from django.conf import settings
import pytz
from datetime import datetime

register = template.Library()


@register.filter
def localtime(value):
    """
    Convert a UTC datetime to the display timezone.
    Usage: {{ timestamp|localtime }}
    """
    if not value:
        return ''
    
    if not isinstance(value, datetime):
        return value
    
    # Get display timezone from settings
    display_tz = pytz.timezone(settings.DISPLAY_TIMEZONE)
    
    # If the datetime is naive, assume it's UTC
    if value.tzinfo is None:
        utc_time = pytz.utc.localize(value)
    else:
        utc_time = value
    
    # Convert to display timezone
    local_time = utc_time.astimezone(display_tz)
    
    return local_time


@register.filter
def format_datetime(value):
    """
    Format a datetime in the display timezone.
    Usage: {{ timestamp|format_datetime }}
    """
    local_time = localtime(value)
    if not local_time:
        return ''
    
    return local_time.strftime('%Y-%m-%d %H:%M:%S')


@register.filter
def format_date(value):
    """
    Format just the date part in the display timezone.
    Usage: {{ timestamp|format_date }}
    """
    local_time = localtime(value)
    if not local_time:
        return ''
    
    return local_time.strftime('%Y-%m-%d')


@register.filter
def format_time(value):
    """
    Format just the time part in the display timezone.
    Usage: {{ timestamp|format_time }}
    """
    local_time = localtime(value)
    if not local_time:
        return ''
    
    return local_time.strftime('%H:%M:%S')


@register.filter
def timezone(value, tz_name):
    """
    Convert a datetime to a specific timezone.
    Usage: {{ timestamp|timezone:"Africa/Nairobi" }}
    """
    if not value:
        return ''
    
    if not isinstance(value, datetime):
        return value
    
    try:
        target_tz = pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        return value
    
    # If the datetime is naive, assume it's UTC
    if value.tzinfo is None:
        utc_time = pytz.utc.localize(value)
    else:
        utc_time = value
    
    # Convert to target timezone
    local_time = utc_time.astimezone(target_tz)
    
    return local_time
