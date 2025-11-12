# Overnight Shift Configuration

## Overview

The system now fully supports overnight/night shifts that cross midnight (e.g., 20:00 to 05:00).

## Configuration

All settings are in your `.env` file:

```properties
# Work Hours Configuration
WORK_START_TIME=20:00          # Shift starts at 8 PM
WORK_END_TIME=05:00            # Shift ends at 5 AM (next day)
OVERNIGHT_SHIFT=True           # MUST be True for overnight shifts

# Outlier Detection Tolerance (in hours)
OUTLIER_EARLY_CLOCK_IN_HOURS=2    # Allow clock-in up to 2 hours before shift start (18:00)
OUTLIER_LATE_CLOCK_IN_HOURS=2     # Allow clock-in up to 2 hours after shift start (22:00)
OUTLIER_EARLY_CLOCK_OUT_HOURS=2   # Allow clock-out up to 2 hours before shift end (03:00)
OUTLIER_LATE_CLOCK_OUT_HOURS=3    # Allow clock-out up to 3 hours after shift end (08:00)
```

## How It Works

### Example: Shift on November 11, 2025

**Your shift: 20:00 (Nov 11) to 05:00 (Nov 12)**

1. **Employee clocks in**: Nov 11 at 20:15
2. **Employee clocks out**: Nov 12 at 05:10

**System behavior:**
- Groups both punches into ONE shift record
- Records the shift date as **Nov 11** (the start date)
- Clock-in: Nov 11 20:15
- Clock-out: Nov 12 05:10
- Calculates total hours: ~9 hours

### Outlier Detection for Your Shift (20:00 - 05:00)

**Valid clock-in window:** 18:00 - 22:00
- Before 18:00 = TOO EARLY (outlier)
- After 22:00 = TOO LATE (outlier)

**Valid clock-out window:** 03:00 - 08:00 (next morning)
- Before 03:00 = TOO EARLY (outlier)
- After 08:00 = TOO LATE (outlier)

## Adjusting Tolerance

If you need to be more lenient (e.g., allow 3 hours early/late):

```properties
OUTLIER_EARLY_CLOCK_IN_HOURS=3
OUTLIER_LATE_CLOCK_IN_HOURS=3
OUTLIER_EARLY_CLOCK_OUT_HOURS=3
OUTLIER_LATE_CLOCK_OUT_HOURS=4
```

This would make:
- Valid clock-in: 17:00 - 23:00
- Valid clock-out: 02:00 - 09:00

## Reprocessing After Changes

After changing any settings in `.env`, reprocess your attendance:

```bash
# Clear existing processed records
python manage.py shell -c "from core.models import ProcessedAttendance; ProcessedAttendance.objects.all().delete()"

# Reprocess with new settings
python manage.py process_attendance
```

## Notes

- The system automatically groups punches across midnight
- Shift date is always the START date (the evening date)
- All times are handled correctly even when crossing midnight
- Raw attendance data is never deleted, only re-processed
