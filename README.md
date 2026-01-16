# ZKTeco F18 Attendance Bridge

A complete Django 4+ application that acts as a local bridge between ZKTeco F18 attendance devices and a remote Django CRM system.

## Features

- **Device Management**: Connect to multiple ZKTeco F18 devices over TCP/IP
- **Automated Polling**: Fetch attendance logs periodically using Celery Beat
- **Smart Processing**: Extract clock-in/clock-out times with outlier detection
- **Overnight Shift Support**: Handles shifts that cross midnight (e.g., 20:00-05:00)
- **CRM Synchronization**: Secure HTTPS sync to remote CRM with retry logic
- **REST API**: Full API for querying attendance data
- **Web Dashboard**: Modern web interface for viewing attendance reports
- **Print Reports**: Clean, printer-friendly daily attendance reports
- **Django Admin**: Comprehensive admin interface for data management
- **Management Commands**: CLI tools for manual operations
- **Environment-based Configuration**: All sensitive data in `.env` file

## Architecture

```
ZKTeco Devices (F18) 
    ↓ (TCP/IP - pyzk)
Local Bridge (This App)
    ├── RawAttendance (all punches)
    ├── ProcessedAttendance (clock-in/out)
    └── Background Tasks (Celery)
        ↓ (HTTPS POST)
Remote CRM System
```

## Requirements

- Python 3.8+
- Redis (for Celery broker)
- ZKTeco F18 devices on local network
- Remote CRM with API endpoint (optional)

## Installation

### 1. Clone or Download

```bash
cd /home/chris/dev/zkteco-f18-attendance-bridge
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` file with your configuration:

```env
# Django
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Timezone
TIME_ZONE=UTC

# Celery/Redis
CELERY_BROKER_URL=redis://localhost:6379/0

# ZKTeco
ZKTECO_DEFAULT_PORT=4370
POLLING_INTERVAL_MINUTES=15

# Work Hours (for outlier detection)
WORK_START_TIME=08:00
WORK_END_TIME=18:00

# CRM
CRM_API_URL=https://your-crm.com/api/attendance/
CRM_API_TOKEN=your-api-token
```

### 5. Create Logs Directory

```bash
mkdir -p logs
```

### 6. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Create Superuser

```bash
python manage.py createsuperuser
```

### 8. Add Devices via Admin

1. Start the server: `python manage.py runserver`
2. Go to http://localhost:8000/admin
3. Add your ZKTeco devices (IP address, port, name)

## Running the Application

### Option 1: Manual Start (Development)

**Terminal 1 - Django Server:**
```bash
python manage.py runserver
```

**Terminal 2 - Celery Worker:**
```bash
celery -A attendance_bridge worker --loglevel=info
```

**Terminal 3 - Celery Beat (Scheduler):**
```bash
celery -A attendance_bridge beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### Option 2: Using Scripts

```bash
# Make scripts executable
chmod +x start_server.sh start_worker.sh start_beat.sh

# Start each component in separate terminals
./start_server.sh
./start_worker.sh
./start_beat.sh
```

## Usage

### Django Admin

Access the admin interface at http://localhost:8000/admin

- **Devices**: Manage ZKTeco devices
- **Raw Attendance**: View all punches from devices
- **Processed Attendance**: View clock-in/out records
- **Periodic Tasks**: Configure Celery Beat schedules

### Management Commands

#### Test Device Connection

```bash
# Test specific IP
python manage.py test_device --ip 192.168.1.100 --port 4370

# Test device from database
python manage.py test_device --device-id 1

# Test all devices
python manage.py test_device --all
```

#### Poll Devices

```bash
# Poll all enabled devices
python manage.py poll_devices

# Poll with time filter
python manage.py poll_devices --since-hours 24
python manage.py poll_devices --since-days 7
```

#### Process Attendance

```bash
# Process all unprocessed attendance
python manage.py process_attendance

# Process specific date range
python manage.py process_attendance --start-date 2025-01-01 --end-date 2025-01-31
```

#### Sync to CRM

```bash
# Sync all unsynced records
python manage.py sync_to_crm

# Sync with limit
python manage.py sync_to_crm --limit 50

# Sync specific date range
python manage.py sync_to_crm --start-date 2025-01-01 --end-date 2025-01-31

# Sync for specific user
python manage.py sync_to_crm --user-id EMP001

# Retry failed syncs
python manage.py sync_to_crm --retry-failed

# Force resync already synced records
python manage.py sync_to_crm --force --start-date 2025-01-01
```

#### Test CRM Connection

```bash
# Test CRM API connection
python manage.py test_crm

# Get sync statistics
python manage.py test_crm --stats
```

### REST API

Base URL: `http://localhost:8000/api/`

Authentication: Session or Token authentication required.

#### Endpoints

**Devices:**
- `GET /api/devices/` - List all devices
- `POST /api/devices/` - Create device
- `GET /api/devices/{id}/` - Get device details
- `GET /api/devices/{id}/info/` - Get device info (from device)
- `POST /api/devices/{id}/poll/` - Poll specific device
- `POST /api/devices/poll_all/` - Poll all devices

**Raw Attendance:**
- `GET /api/raw-attendance/` - List raw attendance
- `GET /api/raw-attendance/?user_id=EMP001` - Filter by user
- `GET /api/raw-attendance/?start_date=2025-01-01&end_date=2025-01-31` - Filter by date range

**Processed Attendance:**
- `GET /api/processed-attendance/` - List processed attendance
- `GET /api/processed-attendance/unsynced/` - Get unsynced records
- `GET /api/processed-attendance/outliers/` - Get outliers
- `GET /api/processed-attendance/stats/` - Get sync statistics
- `POST /api/processed-attendance/process/` - Trigger processing
- `POST /api/processed-attendance/sync/` - Trigger CRM sync

#### Example API Calls

```bash
# Get all processed attendance for a user
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/api/processed-attendance/?user_id=EMP001"

# Get unsynced records
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/api/processed-attendance/unsynced/"

# Get outliers
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/api/processed-attendance/outliers/"

# Trigger device polling
curl -X POST -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/api/devices/poll_all/"

# Trigger CRM sync
curl -X POST -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/api/processed-attendance/sync/"
```

## How It Works

### 1. Device Polling (Every 15 minutes)

- Celery Beat triggers `poll_devices_task`
- Connects to each enabled ZKTeco device via `pyzk`
- Fetches all attendance logs
- Stores in `RawAttendance` (using `get_or_create` to avoid duplicates)
- Updates `Device.last_sync` timestamp

### 2. Processing (Hourly)

- Celery Beat triggers `process_attendance_task`
- Groups raw attendance by user_id and date
- For each group:
  - Earliest punch → `clock_in`
  - Latest punch → `clock_out`
  - Checks if times are outside work hours → sets `is_outlier`
- Stores in `ProcessedAttendance` (using `update_or_create`)

### 3. CRM Sync (Every 30 minutes)

- Celery Beat triggers `sync_to_crm_task`
- Gets unsynced `ProcessedAttendance` records
- Sends each to CRM via HTTPS POST with authentication
- On success: marks `synced_to_crm = True`
- On failure: increments `sync_attempts`, retries later

### 4. Outlier Detection

Records are flagged as outliers if:
- Clock-in is >2 hours before `WORK_START_TIME`
- Clock-in is >2 hours after `WORK_START_TIME`
- Clock-out is >2 hours before `WORK_END_TIME`
- Clock-out is >3 hours after `WORK_END_TIME`

## Database Models

### Device
- Stores ZKTeco device information
- Fields: name, ip_address, port, enabled, last_sync

### RawAttendance
- All punches from devices
- Fields: device, user_id, timestamp, status, punch_state, verify_type
- Unique constraint: (device, user_id, timestamp)

### ProcessedAttendance
- Daily clock-in/clock-out summary
- Fields: device, user_id, date, clock_in, clock_out, is_outlier, synced_to_crm
- Unique constraint: (device, user_id, date)

## Celery Tasks

- `poll_devices` - Poll all devices (every 15 min)
- `process_attendance` - Process raw data (hourly)
- `sync_to_crm` - Sync to CRM (every 30 min)
- `retry_failed_syncs` - Retry failed syncs (every 6 hours)
- `daily_cleanup` - Clean old data (daily at 2 AM)

## Configuration

All configuration is in `.env` file. Key settings:

### Attendance Processing
- `POLLING_INTERVAL_MINUTES` - How often to poll devices
- `WORK_START_TIME` / `WORK_END_TIME` - For outlier detection
- `OVERNIGHT_SHIFT` - Enable overnight shift support (true/false)
- `OVERNIGHT_SHIFT_BUFFER_HOURS` - Buffer hours for shift window

### CRM Synchronization
- `CRM_API_URL` - Remote CRM endpoint
- `CRM_API_TOKEN` - Authentication token
- `CRM_MAX_RETRIES` - Number of retry attempts
- `CRM_SYNC_BATCH_SIZE` - Max records per sync batch

### Email Notifications for Outliers
- `OUTLIER_EMAIL_NOTIFICATIONS` - Enable email alerts for new outliers (true/false)
- `OUTLIER_EMAIL_RECIPIENTS` - Comma-separated list of email addresses
- `EMAIL_BACKEND` - Django email backend (default: console)
- `EMAIL_HOST` - SMTP server hostname
- `EMAIL_PORT` - SMTP server port
- `EMAIL_USE_TLS` - Use TLS (true/false)
- `EMAIL_HOST_USER` - SMTP username
- `EMAIL_HOST_PASSWORD` - SMTP password
- `DEFAULT_FROM_EMAIL` - Sender email address

**Example .env for email notifications:**
```env
OUTLIER_EMAIL_NOTIFICATIONS=true
OUTLIER_EMAIL_RECIPIENTS=manager@company.com,hr@company.com
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=attendance@company.com
```

## Production Deployment

### Using Supervisor

Create `/etc/supervisor/conf.d/attendance_bridge.conf`:

```ini
[program:attendance_bridge_web]
command=/path/to/venv/bin/gunicorn attendance_bridge.wsgi:application --bind 0.0.0.0:8000
directory=/path/to/zkteco-f18-attendance-bridge
user=www-data
autostart=true
autorestart=true

[program:attendance_bridge_worker]
command=/path/to/venv/bin/celery -A attendance_bridge worker --loglevel=info
directory=/path/to/zkteco-f18-attendance-bridge
user=www-data
autostart=true
autorestart=true

[program:attendance_bridge_beat]
command=/path/to/venv/bin/celery -A attendance_bridge beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
directory=/path/to/zkteco-f18-attendance-bridge
user=www-data
autostart=true
autorestart=true
```

### Using systemd

Create service files in `/etc/systemd/system/`:

**attendance-bridge-web.service**
**attendance-bridge-worker.service**
**attendance-bridge-beat.service**

## Troubleshooting

### Can't connect to device

```bash
# Test connectivity
ping 192.168.1.100

# Test device connection
python manage.py test_device --ip 192.168.1.100

# Check device port (default 4370)
# Ensure device is on same network
# Check firewall rules
```

### CRM sync failing

```bash
# Test CRM connection
python manage.py test_crm

# Check .env file for correct CRM_API_URL and CRM_API_TOKEN
# View sync statistics
python manage.py test_crm --stats

# Manually retry failed syncs
python manage.py sync_to_crm --retry-failed
```

### Celery not running tasks

```bash
# Check Redis is running
redis-cli ping

# Check Celery worker logs
# Check Celery beat logs
# Verify CELERY_BROKER_URL in .env
```

### No data appearing

```bash
# 1. Check devices are enabled in admin
# 2. Manually poll a device
python manage.py poll_devices

# 3. Check raw attendance created
python manage.py shell
>>> from core.models import RawAttendance
>>> RawAttendance.objects.count()

# 4. Process attendance
python manage.py process_attendance

# 5. Check processed attendance
>>> from core.models import ProcessedAttendance
>>> ProcessedAttendance.objects.count()
```

## Security Notes

- Always use HTTPS for CRM communication
- Store `.env` file securely (never commit to git)
- Use strong `DJANGO_SECRET_KEY`
- Set `DEBUG=False` in production
- Configure proper `ALLOWED_HOSTS`
- Use database authentication
- Restrict API access with authentication

## License

This project is proprietary. All rights reserved.

## Support

For issues or questions, contact your system administrator.
