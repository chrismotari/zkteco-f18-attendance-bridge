# Timezone Handling Documentation

## Overview

The system now supports proper timezone handling for ZKTeco devices. Since ZKTeco devices store attendance data as **timezone-naive timestamps** (without timezone information), we need to manually configure each device's timezone to correctly interpret the data.

## How It Works

### 1. Storage (Database)
- All timestamps are stored in **UTC** in the database
- This is Django's default (`TIME_ZONE = 'UTC'` in settings.py)
- Models: `RawAttendance.timestamp`, `ProcessedAttendance.clock_in/clock_out`, `Device.last_sync`

### 2. Device Configuration
- Each `Device` has a `timezone` field (default: `Africa/Nairobi`)
- When creating/editing devices, select the appropriate timezone from the dropdown
- Common timezones included:
  - UTC
  - Africa/Nairobi (EAT - UTC+3)
  - Africa/Lagos (WAT - UTC+1)
  - Africa/Johannesburg (SAST - UTC+2)
  - Europe/London (GMT/BST)
  - America/New_York (EST/EDT)
  - Asia/Dubai (GST - UTC+4)

### 3. Data Fetching (Device → Database)
When polling attendance data from a device:

```python
# In device_utils.py fetch_attendance()
device_tz = pytz.timezone(device.timezone)  # e.g., 'Africa/Nairobi'

# Device gives us naive timestamp: 2024-01-08 10:30:00
# We localize it to device timezone
local_timestamp = device_tz.localize(attendance.timestamp)

# Then convert to UTC for storage
utc_timestamp = local_timestamp.astimezone(pytz.utc)
```

**Example:**
- Device shows: `2024-01-08 10:30:00` (no timezone info)
- Device timezone: `Africa/Nairobi` (UTC+3)
- Interpreted as: `2024-01-08 10:30:00 EAT`
- Stored as: `2024-01-08 07:30:00 UTC`

### 4. Display (Database → User Interface)
When displaying timestamps in templates:

```django
{% load timezone_filters %}

<!-- Full datetime -->
{{ attendance.clock_in|format_datetime }}  {# 2024-01-08 10:30:00 #}

<!-- Just time -->
{{ attendance.clock_in|format_time }}  {# 10:30:00 #}

<!-- Just date -->
{{ attendance.clock_in|format_date }}  {# 2024-01-08 #}
```

The display timezone is configured in `settings.py`:
```python
DISPLAY_TIMEZONE = 'Africa/Nairobi'  # Can be changed via environment variable
```

**Example:**
- Stored in DB: `2024-01-08 07:30:00 UTC`
- Display timezone: `Africa/Nairobi` (UTC+3)
- Displayed as: `2024-01-08 10:30:00`

## Configuration

### Environment Variables

Add to `.env` or environment:

```bash
# Display timezone for frontend (users see times in this timezone)
DISPLAY_TIMEZONE=Africa/Nairobi

# Keep this as UTC for database storage
TIME_ZONE=UTC
```

### Device Setup

1. **Create/Edit Device**: Go to Devices page
2. **Select Timezone**: Choose the timezone where the physical device is located
3. **Save**: The timezone is stored with the device configuration

## Important Notes

### ✅ DO:
- Set the correct timezone for each device based on its physical location
- Use the template filters (`format_datetime`, `format_time`, `format_date`) in templates
- Keep `TIME_ZONE = 'UTC'` in settings.py for database storage

### ❌ DON'T:
- Change `TIME_ZONE` setting from UTC (it affects database storage)
- Mix up device timezone (where device is) with display timezone (what users see)
- Use Django's built-in `|date` filter for times - use custom filters instead

## Timezone Flow Diagram

```
┌─────────────────┐
│ ZKTeco Device   │ 10:30:00 (naive, no TZ info)
│ Location: Kenya │
└────────┬────────┘
         │
         │ 1. Poll data
         ▼
┌─────────────────┐
│ device_utils.py │ Localize to Africa/Nairobi (EAT)
│                 │ → 2024-01-08 10:30:00 EAT
└────────┬────────┘
         │
         │ 2. Convert to UTC
         ▼
┌─────────────────┐
│ Database (UTC)  │ → 2024-01-08 07:30:00 UTC
└────────┬────────┘
         │
         │ 3. Retrieve & display
         ▼
┌─────────────────┐
│ Template Filter │ Convert UTC → DISPLAY_TIMEZONE
│                 │ → 2024-01-08 10:30:00 (shown to user)
└─────────────────┘
```

## Affected Files

### Models
- `core/models.py` - Added `timezone` field to `Device` model

### Views
- `core/views.py` - Updated `device_create` and `device_edit` to save timezone

### Device Communication
- `core/device_utils.py` - `fetch_attendance()` converts device time → UTC

### Templates
- `core/templates/core/device_form.html` - Timezone selector
- `core/templates/core/devices.html` - Timezone selector in create form
- `core/templates/core/attendance_report.html` - Uses timezone filters
- `core/templates/core/attendance_print.html` - Uses timezone filters
- `core/templates/core/device_users.html` - Uses timezone filters
- `core/templates/core/dashboard.html` - Uses timezone filters

### Template Tags
- `core/templatetags/timezone_filters.py` - Custom filters for timezone conversion

### Settings
- `attendance_bridge/settings.py` - `DISPLAY_TIMEZONE` configuration

## Testing

Test the timezone handling:

```bash
# 1. Create a test device with a specific timezone
python3 manage.py shell
>>> from core.models import Device
>>> device = Device.objects.create(
...     name="Test Device",
...     ip_address="192.168.1.100",
...     timezone="Africa/Nairobi"
... )

# 2. Poll data
python3 manage.py poll_devices --device <device_id>

# 3. Check the timestamps
>>> from core.models import RawAttendance
>>> att = RawAttendance.objects.latest('timestamp')
>>> print(f"Stored (UTC): {att.timestamp}")
>>> import pytz
>>> nairobi = pytz.timezone('Africa/Nairobi')
>>> print(f"Local time: {att.timestamp.replace(tzinfo=pytz.utc).astimezone(nairobi)}")
```

## Troubleshooting

### Issue: Times are off by X hours
**Solution**: Check that the device's timezone is correctly configured. The offset should match the device's physical location.

### Issue: Duplicate attendance records
**Solution**: Not related to timezone. This is a data quality issue - check device settings for duplicate punch prevention.

### Issue: Template filter not working
**Solution**: Make sure `{% load timezone_filters %}` is at the top of the template file.

### Issue: Getting naive datetime warnings
**Solution**: All datetimes should be timezone-aware. Check that `USE_TZ = True` in settings.py.

## Migration History

- `0005_add_device_timezone.py` - Added timezone field to Device model (default: Africa/Nairobi)
