# Django Attendance Bridge - Complete Application

## 🎉 Project Complete!

This is a fully functional Django 4+ application that acts as a local bridge between ZKTeco F18 attendance devices and a remote Django CRM system.

## 📦 What's Included

### Core Functionality
✅ **Device Management** - Connect to multiple ZKTeco F18 devices  
✅ **Automated Polling** - Fetch attendance logs every 15 minutes  
✅ **Smart Processing** - Extract clock-in/out with outlier detection  
✅ **CRM Synchronization** - Secure HTTPS sync with retry logic  
✅ **REST API** - Full API for querying attendance data  
✅ **Django Admin** - Comprehensive admin interface  
✅ **Management Commands** - CLI tools for all operations  
✅ **Background Tasks** - Celery + Redis for automation  
✅ **Environment Configuration** - All config in .env file  
✅ **Comprehensive Logging** - Track all operations  

### Files Created (37 files)

**Main Project:**
- `manage.py` - Django management script
- `setup.sh` - Automated setup script
- `requirements.txt` - Python dependencies
- `.env.example` - Environment template
- `.gitignore` - Git ignore rules

**Documentation:**
- `README.md` - Complete documentation
- `SETUP.md` - Step-by-step setup guide
- `API_DOCS.md` - REST API reference
- `PROJECT_STRUCTURE.md` - Code organization
- `QUICKREF.md` - Quick reference card

**Scripts:**
- `start_server.sh` - Start Django server
- `start_worker.sh` - Start Celery worker
- `start_beat.sh` - Start Celery Beat

**Django Project (`attendance_bridge/`):**
- `__init__.py` - Imports Celery app
- `settings.py` - Configuration (reads .env)
- `urls.py` - URL routing
- `wsgi.py` - WSGI application
- `asgi.py` - ASGI application
- `celery.py` - Celery configuration

**Core App (`core/`):**
- `models.py` - Database models (Device, RawAttendance, ProcessedAttendance)
- `admin.py` - Django admin interface
- `serializers.py` - REST API serializers
- `views.py` - REST API views
- `urls.py` - API URL routing
- `device_utils.py` - ZKTeco device functions
- `processing_utils.py` - Attendance processing
- `crm_utils.py` - CRM synchronization
- `tasks.py` - Celery background tasks
- `celery_schedules.py` - Celery Beat schedule
- `apps.py` - App configuration

**Management Commands (`core/management/commands/`):**
- `poll_devices.py` - Manual device polling
- `process_attendance.py` - Manual processing
- `sync_to_crm.py` - Manual CRM sync
- `test_device.py` - Test device connection
- `test_crm.py` - Test CRM connection

## 🚀 Quick Start

```bash
# 1. Run automated setup
./setup.sh

# 2. Configure environment
cp .env.example .env
nano .env  # Add your CRM_API_URL and CRM_API_TOKEN

# 3. Start services (3 separate terminals)
./start_server.sh    # Terminal 1: Django web server
./start_worker.sh    # Terminal 2: Celery worker
./start_beat.sh      # Terminal 3: Celery Beat scheduler

# 4. Access admin
# Open http://localhost:8000/admin
# Add your ZKTeco devices

# 5. Test the system
python manage.py test_device --all
python manage.py poll_devices
python manage.py process_attendance
python manage.py test_crm
python manage.py sync_to_crm --limit 5
```

## 📊 System Architecture

```
┌──────────────────────┐
│  ZKTeco F18 Devices  │
│  (Multiple devices)  │
└──────────┬───────────┘
           │ TCP/IP (pyzk)
           │ Poll every 15 min
           ▼
┌─────────────────────────┐
│   RawAttendance DB      │ ← All punches stored
│   - user_id             │
│   - timestamp           │
│   - status              │
└──────────┬──────────────┘
           │ Process hourly
           │ Extract clock-in/out
           │ Detect outliers
           ▼
┌─────────────────────────┐
│ ProcessedAttendance DB  │ ← Daily summary
│   - user_id             │
│   - date                │
│   - clock_in            │
│   - clock_out           │
│   - is_outlier          │
└──────────┬──────────────┘
           │ Sync every 30 min
           │ HTTPS POST
           ▼
┌─────────────────────────┐
│   Remote CRM System     │
│   (Your backend)        │
└─────────────────────────┘
```

## 🔧 Key Features Explained

### 1. Device Polling (Automated - Every 15 min)
- Connects to each ZKTeco device via TCP/IP using `pyzk`
- Fetches all attendance logs
- Stores in `RawAttendance` table (avoids duplicates)
- Updates device's last_sync timestamp

### 2. Processing (Automated - Hourly)
- Groups raw attendance by user and date
- Identifies earliest punch = clock_in
- Identifies latest punch = clock_out
- Flags outliers (outside work hours)
- Stores in `ProcessedAttendance` table

### 3. Outlier Detection
Records flagged as outliers if:
- Clock-in >2 hours before WORK_START_TIME
- Clock-in >2 hours after WORK_START_TIME
- Clock-out >2 hours before WORK_END_TIME
- Clock-out >3 hours after WORK_END_TIME

### 4. CRM Sync (Automated - Every 30 min)
- Gets unsynced ProcessedAttendance records
- Sends to remote CRM via HTTPS POST
- Authenticates with token from .env
- Retries on failure (max 3 attempts)
- Marks records as synced on success

### 5. REST API
- Full CRUD for devices
- Read-only for attendance records
- Custom actions: poll, process, sync
- Token/Session authentication
- Pagination and filtering

## 📝 Database Models

### Device
```python
- name: CharField (unique)
- ip_address: GenericIPAddressField
- port: IntegerField (default 4370)
- enabled: BooleanField
- last_sync: DateTimeField
```

### RawAttendance
```python
- device: ForeignKey(Device)
- user_id: CharField (indexed)
- timestamp: DateTimeField (indexed)
- status: IntegerField
- punch_state: IntegerField
- verify_type: IntegerField
# Unique: (device, user_id, timestamp)
```

### ProcessedAttendance
```python
- device: ForeignKey(Device)
- user_id: CharField (indexed)
- date: DateField (indexed)
- clock_in: DateTimeField
- clock_out: DateTimeField
- is_outlier: BooleanField
- outlier_reason: TextField
- synced_to_crm: BooleanField
- sync_attempts: IntegerField
- last_sync_attempt: DateTimeField
# Unique: (device, user_id, date)
```

## 🔐 Security Features

1. **Environment Variables** - All sensitive data in .env
2. **Token Authentication** - CRM API uses secure tokens
3. **HTTPS Support** - Encrypted communication to CRM
4. **Retry Logic** - Automatic retry with exponential backoff
5. **Django Admin Auth** - Built-in user authentication
6. **REST API Auth** - Session/Token required
7. **No Hardcoded Secrets** - Everything configurable
8. **Secure Logging** - Errors logged, not exposed

## 📋 Available Commands

### Management Commands
```bash
python manage.py poll_devices
python manage.py process_attendance
python manage.py sync_to_crm
python manage.py test_device --all
python manage.py test_crm --stats
```

### API Endpoints
```bash
GET  /api/devices/
POST /api/devices/poll_all/
GET  /api/raw-attendance/
GET  /api/processed-attendance/
GET  /api/processed-attendance/unsynced/
GET  /api/processed-attendance/outliers/
POST /api/processed-attendance/sync/
```

### Celery Tasks (Automated)
- `poll_devices` - Every 15 minutes
- `process_attendance` - Every hour
- `sync_to_crm` - Every 30 minutes
- `retry_failed_syncs` - Every 6 hours
- `daily_cleanup` - Daily at 2 AM

## 🛠️ Technologies Used

- **Django 4+** - Web framework
- **Django REST Framework** - API
- **Celery** - Background tasks
- **Redis** - Message broker
- **pyzk** - ZKTeco device communication
- **requests** - HTTP client
- **python-dotenv** - Environment configuration
- **SQLite** - Database (can use PostgreSQL)

## 📚 Documentation Files

1. **README.md** - Complete documentation with all features
2. **SETUP.md** - Step-by-step setup instructions
3. **API_DOCS.md** - REST API reference with examples
4. **PROJECT_STRUCTURE.md** - Code organization guide
5. **QUICKREF.md** - Quick reference for common tasks

## ✅ Production Readiness

The application includes:
- ✅ Proper error handling
- ✅ Comprehensive logging
- ✅ Database migrations
- ✅ Admin interface
- ✅ API documentation
- ✅ Environment-based config
- ✅ Background task processing
- ✅ Retry mechanisms
- ✅ Security best practices
- ✅ Modular code structure

## 🎯 Next Steps

1. **Configure .env file** with your settings
2. **Install Redis** if not already installed
3. **Run setup script**: `./setup.sh`
4. **Add devices** in Django admin
5. **Test connections** with management commands
6. **Start all services** with provided scripts
7. **Monitor logs** in `logs/attendance_bridge.log`
8. **Configure production** deployment when ready

## 📞 Support & Troubleshooting

All common issues and solutions are documented in:
- README.md (Troubleshooting section)
- SETUP.md (Common Issues section)
- QUICKREF.md (Troubleshooting section)

## 🎓 Learning Resources

To understand the codebase:
1. Start with `PROJECT_STRUCTURE.md` for overview
2. Read `models.py` to understand data structure
3. Check `device_utils.py` for device communication
4. Review `processing_utils.py` for processing logic
5. Study `crm_utils.py` for sync implementation
6. Look at `tasks.py` for automation

## 🚀 Deployment

For production deployment:
- Use PostgreSQL instead of SQLite
- Use Gunicorn/uWSGI for serving
- Configure Nginx as reverse proxy
- Use Supervisor/systemd for process management
- Enable SSL/TLS certificates
- Set DEBUG=False in .env
- Configure proper ALLOWED_HOSTS

See README.md for detailed production setup.

---

## 📄 License

Proprietary - All rights reserved

## 🙏 Acknowledgments

Built with Django, Celery, and the pyzk library.

---

**Ready to run!** Start with `./setup.sh` and follow the prompts.
