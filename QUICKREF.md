# Quick Reference - Django Attendance Bridge

## Quick Start

```bash
# 1. Run setup
./setup.sh

# 2. Edit .env with your settings
nano .env

# 3. Start services (3 terminals)
./start_server.sh    # Terminal 1
./start_worker.sh    # Terminal 2
./start_beat.sh      # Terminal 3

# 4. Add devices at http://localhost:8000/admin
```

## Common Commands

### Management Commands

```bash
# Poll all devices
python manage.py poll_devices

# Process attendance
python manage.py process_attendance

# Sync to CRM
python manage.py sync_to_crm

# Test device connection
python manage.py test_device --ip 192.168.1.100
python manage.py test_device --all

# Test CRM connection
python manage.py test_crm
python manage.py test_crm --stats

# Sync specific date range
python manage.py sync_to_crm --start-date 2025-01-01 --end-date 2025-01-31

# Retry failed syncs
python manage.py sync_to_crm --retry-failed
```

### Django Commands

```bash
# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver

# Django shell
python manage.py shell
```

### Celery Commands

```bash
# Start worker
celery -A attendance_bridge worker --loglevel=info

# Start beat scheduler
celery -A attendance_bridge beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Inspect active tasks
celery -A attendance_bridge inspect active

# Purge all tasks
celery -A attendance_bridge purge
```

## API Endpoints

### Base URL
```
http://localhost:8000/api/
```

### Authentication
```bash
# Add to headers
Authorization: Token YOUR_TOKEN_HERE
```

### Key Endpoints

```bash
# Devices
GET    /api/devices/
POST   /api/devices/
GET    /api/devices/{id}/info/
POST   /api/devices/{id}/poll/
POST   /api/devices/poll_all/

# Raw Attendance
GET    /api/raw-attendance/
GET    /api/raw-attendance/?user_id=EMP001

# Processed Attendance
GET    /api/processed-attendance/
GET    /api/processed-attendance/unsynced/
GET    /api/processed-attendance/outliers/
GET    /api/processed-attendance/stats/
POST   /api/processed-attendance/process/
POST   /api/processed-attendance/sync/
```

## Configuration (.env)

### Required Settings
```env
DJANGO_SECRET_KEY=your-secret-key
CRM_API_URL=https://your-crm.com/api/attendance/
CRM_API_TOKEN=your-token
```

### Optional Settings
```env
TIME_ZONE=UTC
WORK_START_TIME=08:00
WORK_END_TIME=18:00
POLLING_INTERVAL_MINUTES=15
LOG_LEVEL=INFO
```

## Directory Structure

```
zkteco-f18-attendance-bridge/
├── manage.py
├── .env                    # Your configuration
├── requirements.txt        # Dependencies
├── setup.sh               # Setup script
├── start_*.sh             # Start scripts
│
├── attendance_bridge/     # Django project
│   ├── settings.py       # Settings (reads .env)
│   ├── urls.py
│   └── celery.py         # Celery config
│
├── core/                  # Main app
│   ├── models.py         # Device, RawAttendance, ProcessedAttendance
│   ├── device_utils.py   # ZKTeco connection
│   ├── processing_utils.py # Process attendance
│   ├── crm_utils.py      # CRM sync
│   ├── tasks.py          # Celery tasks
│   ├── views.py          # REST API
│   └── management/commands/ # CLI commands
│
└── logs/                  # Log files
```

## Troubleshooting

### Can't connect to device
```bash
ping 192.168.1.100
python manage.py test_device --ip 192.168.1.100
# Check device is on, same network, port 4370 open
```

### CRM sync failing
```bash
python manage.py test_crm
# Check CRM_API_URL and CRM_API_TOKEN in .env
# Verify CRM endpoint is accessible
```

### Celery not working
```bash
redis-cli ping  # Should return PONG
# Check CELERY_BROKER_URL in .env
# Restart worker and beat
```

### No data appearing
```bash
# 1. Check devices enabled in admin
# 2. Manually poll
python manage.py poll_devices
# 3. Check raw data created
python manage.py shell
>>> from core.models import RawAttendance
>>> RawAttendance.objects.count()
# 4. Process
python manage.py process_attendance
# 5. Check processed
>>> from core.models import ProcessedAttendance
>>> ProcessedAttendance.objects.count()
```

## Database Queries (Shell)

```python
python manage.py shell

# Import models
from core.models import Device, RawAttendance, ProcessedAttendance
from django.utils import timezone

# Get all devices
devices = Device.objects.all()

# Get attendance for user
attendance = ProcessedAttendance.objects.filter(user_id='EMP001')

# Get today's attendance
from datetime import date
today = ProcessedAttendance.objects.filter(date=date.today())

# Get unsynced
unsynced = ProcessedAttendance.objects.filter(synced_to_crm=False)

# Get outliers
outliers = ProcessedAttendance.objects.filter(is_outlier=True)

# Count records
RawAttendance.objects.count()
ProcessedAttendance.objects.filter(synced_to_crm=True).count()
```

## Logs

```bash
# Application logs
tail -f logs/attendance_bridge.log

# Watch logs in real-time
tail -f logs/attendance_bridge.log | grep ERROR
```

## URLs

- Admin: http://localhost:8000/admin
- API Root: http://localhost:8000/api/
- API Devices: http://localhost:8000/api/devices/
- API Processed: http://localhost:8000/api/processed-attendance/

## Service Status

```bash
# Check Redis
redis-cli ping

# Check Django server
curl http://localhost:8000/api/

# Check if worker is running
ps aux | grep celery

# Check database
python manage.py dbshell
```

## Backup

```bash
# Backup database
cp db.sqlite3 db.sqlite3.backup

# Export data
python manage.py dumpdata > backup.json

# Import data
python manage.py loaddata backup.json
```

## Useful Filters

### Date Range Queries
```python
from datetime import date, timedelta
start = date.today() - timedelta(days=7)
end = date.today()
records = ProcessedAttendance.objects.filter(date__gte=start, date__lte=end)
```

### User Queries
```python
user_records = ProcessedAttendance.objects.filter(user_id='EMP001').order_by('-date')
```

### Outlier Analysis
```python
outliers = ProcessedAttendance.objects.filter(is_outlier=True, date__gte=start)
for record in outliers:
    print(f"{record.user_id} on {record.date}: {record.outlier_reason}")
```

## Performance Tips

1. **Index frequently queried fields** (already done in models)
2. **Use select_related** for foreign keys
3. **Batch operations** when possible
4. **Monitor Redis** memory usage
5. **Clean old logs** periodically

## Security Checklist

- [ ] Change DJANGO_SECRET_KEY in .env
- [ ] Set DEBUG=False in production
- [ ] Configure ALLOWED_HOSTS properly
- [ ] Use HTTPS for CRM communication
- [ ] Secure .env file permissions (chmod 600)
- [ ] Enable firewall on server
- [ ] Use strong admin password
- [ ] Regularly update dependencies

## Documentation

- README.md - Full documentation
- SETUP.md - Setup instructions
- API_DOCS.md - API reference
- PROJECT_STRUCTURE.md - Code structure
- QUICKREF.md - This file
