# Project Structure

```
zkteco-f18-attendance-bridge/
├── manage.py                      # Django management script
├── setup.sh                       # Automated setup script
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment configuration template
├── .gitignore                     # Git ignore rules
│
├── README.md                      # Main documentation
├── SETUP.md                       # Setup guide
├── API_DOCS.md                    # API documentation
│
├── start_server.sh                # Start Django server
├── start_worker.sh                # Start Celery worker
├── start_beat.sh                  # Start Celery Beat scheduler
│
├── attendance_bridge/             # Main Django project
│   ├── __init__.py               # Package init (imports Celery)
│   ├── settings.py               # Django settings (reads from .env)
│   ├── urls.py                   # URL routing
│   ├── wsgi.py                   # WSGI application
│   ├── asgi.py                   # ASGI application
│   └── celery.py                 # Celery configuration
│
├── core/                          # Main application
│   ├── __init__.py
│   ├── apps.py                   # App configuration
│   ├── models.py                 # Database models
│   │   ├── Device              # ZKTeco device info
│   │   ├── RawAttendance       # Raw punches from devices
│   │   └── ProcessedAttendance # Clock-in/out records
│   │
│   ├── admin.py                  # Django admin configuration
│   ├── serializers.py            # REST API serializers
│   ├── views.py                  # REST API views
│   ├── urls.py                   # API URL routing
│   │
│   ├── device_utils.py           # Device polling utilities
│   │   ├── connect_device()    # Connect to ZKTeco device
│   │   ├── fetch_attendance()  # Fetch logs from device
│   │   ├── poll_all_devices()  # Poll all enabled devices
│   │   ├── get_device_info()   # Get device information
│   │   └── test_device_connection() # Test connection
│   │
│   ├── processing_utils.py       # Attendance processing
│   │   ├── process_attendance_for_date() # Process single date
│   │   ├── process_all_unprocessed_attendance() # Process all
│   │   ├── is_outlier()        # Check if outlier
│   │   ├── deduplicate_records() # Remove duplicates
│   │   └── normalize_attendance() # Reprocess records
│   │
│   ├── crm_utils.py              # CRM synchronization
│   │   ├── send_to_crm()       # Send single record
│   │   ├── sync_batch()        # Sync multiple records
│   │   ├── sync_unsynced_attendance() # Sync unsynced
│   │   ├── sync_by_date_range() # Sync date range
│   │   ├── sync_by_user()      # Sync specific user
│   │   └── test_crm_connection() # Test CRM API
│   │
│   ├── tasks.py                  # Celery tasks
│   │   ├── poll_devices_task   # Periodic device polling
│   │   ├── process_attendance_task # Periodic processing
│   │   ├── sync_to_crm_task    # Periodic CRM sync
│   │   ├── retry_failed_syncs_task # Retry failures
│   │   └── daily_cleanup_task  # Daily maintenance
│   │
│   ├── celery_schedules.py       # Celery Beat schedule config
│   │
│   └── management/               # Management commands
│       └── commands/
│           ├── poll_devices.py  # Manual device polling
│           ├── process_attendance.py # Manual processing
│           ├── sync_to_crm.py   # Manual CRM sync
│           ├── test_device.py   # Test device connection
│           └── test_crm.py      # Test CRM connection
│
├── logs/                          # Log files (created on first run)
│   └── attendance_bridge.log
│
└── db.sqlite3                     # SQLite database (created after migrate)
```

## Key Files Explained

### Configuration Files

- **`.env`**: All sensitive configuration (API tokens, URLs, work hours)
- **`requirements.txt`**: Python package dependencies
- **`settings.py`**: Django settings, reads from `.env`

### Models (core/models.py)

- **Device**: Stores ZKTeco device info (IP, port, name, last sync)
- **RawAttendance**: All punches from devices (user_id, timestamp, status)
- **ProcessedAttendance**: Daily summary (clock_in, clock_out, outlier flag)

### Utilities (core/)

- **device_utils.py**: Connect to ZKTeco devices using `pyzk` library
- **processing_utils.py**: Process raw punches into clock-in/out
- **crm_utils.py**: Sync to remote CRM via HTTPS POST

### Background Tasks (core/tasks.py)

- Automated device polling (every 15 min)
- Automated processing (hourly)
- Automated CRM sync (every 30 min)
- Retry failed syncs (every 6 hours)
- Daily cleanup (2 AM)

### Management Commands

All available via `python manage.py <command>`:

- `poll_devices` - Manually poll devices
- `process_attendance` - Manually process attendance
- `sync_to_crm` - Manually sync to CRM
- `test_device` - Test device connection
- `test_crm` - Test CRM connection

### REST API (core/views.py, core/urls.py)

- `/api/devices/` - Device management
- `/api/raw-attendance/` - Raw attendance logs
- `/api/processed-attendance/` - Processed records
- Custom actions: poll, sync, process, stats

## Data Flow

```
┌─────────────────┐
│ ZKTeco Devices  │
│  (F18 Models)   │
└────────┬────────┘
         │ TCP/IP (pyzk)
         │ Polling every 15min
         ▼
┌─────────────────────┐
│  RawAttendance      │  ← All punches stored here
│  (Database Table)   │
└────────┬────────────┘
         │ Processing (hourly)
         │ Extract clock-in/out
         │ Detect outliers
         ▼
┌──────────────────────┐
│ ProcessedAttendance  │  ← Daily summary stored here
│  (Database Table)    │
└────────┬─────────────┘
         │ CRM Sync (every 30min)
         │ HTTPS POST
         ▼
┌─────────────────────┐
│  Remote CRM System  │
│  (Your Backend)     │
└─────────────────────┘
```

## Background Processes

### Celery Worker
- Executes tasks from queue
- Handles device polling, processing, syncing
- Should always be running

### Celery Beat
- Scheduler that triggers periodic tasks
- Reads schedule from database (django-celery-beat)
- Should always be running

### Redis
- Message broker for Celery
- Stores task queue and results
- Must be running for Celery to work

## Environment Variables

All in `.env` file:

**Django:**
- `DJANGO_SECRET_KEY` - Secret key for Django
- `DEBUG` - Debug mode (True/False)
- `ALLOWED_HOSTS` - Allowed host names

**Database:**
- Uses SQLite by default (db.sqlite3)
- Can configure PostgreSQL via DATABASE_URL

**Celery:**
- `CELERY_BROKER_URL` - Redis connection
- `CELERY_RESULT_BACKEND` - Redis connection

**ZKTeco:**
- `ZKTECO_DEFAULT_PORT` - Device port (default: 4370)
- `ZKTECO_TIMEOUT` - Connection timeout
- `POLLING_INTERVAL_MINUTES` - Polling frequency

**Work Hours:**
- `WORK_START_TIME` - Work start (HH:MM)
- `WORK_END_TIME` - Work end (HH:MM)

**CRM:**
- `CRM_API_URL` - Remote CRM endpoint
- `CRM_API_TOKEN` - API authentication token
- `CRM_SYNC_BATCH_SIZE` - Records per batch
- `CRM_REQUEST_TIMEOUT` - Request timeout
- `CRM_MAX_RETRIES` - Retry attempts

## Security Features

1. **No hardcoded credentials** - All in `.env`
2. **Token authentication** - CRM API uses token auth
3. **HTTPS support** - Secure communication to CRM
4. **Retry logic** - Automatic retry with backoff
5. **Django admin** - Built-in authentication
6. **REST API auth** - Session/Token required
7. **Error logging** - All errors logged securely

## Monitoring

### Log Files
- `logs/attendance_bridge.log` - Application logs
- Console output - Celery worker/beat logs

### Django Admin
- http://localhost:8000/admin
- View all models
- Check sync status
- Manage devices

### API Endpoints
- `/api/processed-attendance/stats/` - Sync statistics
- `/api/devices/{id}/info/` - Device status

### Management Commands
```bash
python manage.py test_crm --stats    # Sync statistics
python manage.py test_device --all   # Test all devices
```

## Deployment

### Development
- SQLite database
- Django development server
- Separate terminals for worker/beat

### Production
- PostgreSQL/MySQL database
- Gunicorn/uWSGI server
- Nginx reverse proxy
- Supervisor/systemd for processes
- SSL/TLS certificates

See README.md for production deployment guide.
