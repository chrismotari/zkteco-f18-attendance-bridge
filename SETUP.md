# Quick Setup Guide

## Prerequisites

1. **Python 3.8+**
   ```bash
   python3 --version
   ```

2. **Redis Server**
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install redis-server
   sudo systemctl start redis
   sudo systemctl enable redis
   
   # macOS
   brew install redis
   brew services start redis
   
   # Verify
   redis-cli ping  # Should return PONG
   ```

3. **ZKTeco Devices**
   - Ensure devices are on the same network
   - Note down IP addresses
   - Default port is usually 4370

## Step-by-Step Setup

### 1. Install Python Dependencies

```bash
cd /home/chris/dev/zkteco-f18-attendance-bridge

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install packages
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env file
nano .env  # or use your preferred editor
```

**Required settings in .env:**
```env
DJANGO_SECRET_KEY=your-secret-key-change-this
CRM_API_URL=https://your-crm-domain.com/api/attendance/
CRM_API_TOKEN=your-crm-api-token
```

**Optional settings:**
```env
TIME_ZONE=America/New_York
WORK_START_TIME=09:00
WORK_END_TIME=17:00
POLLING_INTERVAL_MINUTES=15
```

### 3. Initialize Database

```bash
# Create logs directory
mkdir -p logs

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser for admin access
python manage.py createsuperuser
```

### 4. Add Devices

```bash
# Start Django server
python manage.py runserver

# Open browser: http://localhost:8000/admin
# Login with superuser credentials
# Go to "Devices" section
# Click "Add Device"
# Fill in:
#   - Name: Main Office Device
#   - IP Address: 192.168.1.100
#   - Port: 4370
#   - Enabled: ✓
# Save
```

### 5. Test Device Connection

```bash
# Test specific device
python manage.py test_device --ip 192.168.1.100

# Should show:
# ✓ Connection successful! Firmware: Ver X.X.X, Serial: XXXXXXXX
```

### 6. Test CRM Connection

```bash
python manage.py test_crm

# Should show:
# ✓ CRM API connection successful
```

### 7. Manual First Sync

```bash
# Poll devices
python manage.py poll_devices

# Process attendance
python manage.py process_attendance

# Sync to CRM
python manage.py sync_to_crm --limit 10
```

### 8. Start Background Tasks

**Option A: Development (3 terminals)**

Terminal 1:
```bash
python manage.py runserver
```

Terminal 2:
```bash
celery -A attendance_bridge worker --loglevel=info
```

Terminal 3:
```bash
celery -A attendance_bridge beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

**Option B: Using scripts**

```bash
chmod +x start_server.sh start_worker.sh start_beat.sh

# Terminal 1
./start_server.sh

# Terminal 2
./start_worker.sh

# Terminal 3
./start_beat.sh
```

## Verification

### Check Everything is Working

1. **Django Admin** - http://localhost:8000/admin
   - Should show devices, attendance records

2. **API** - http://localhost:8000/api/
   - Should show API root

3. **Celery Worker**
   - Should show: "celery@hostname ready"

4. **Celery Beat**
   - Should show scheduled tasks

5. **Poll Test**
   ```bash
   python manage.py poll_devices
   ```
   - Should fetch attendance from devices

6. **Process Test**
   ```bash
   python manage.py process_attendance
   ```
   - Should create processed records

7. **Sync Test**
   ```bash
   python manage.py sync_to_crm --limit 1
   ```
   - Should sync to CRM

## Common Issues

### "Connection refused" to Redis

```bash
# Check if Redis is running
sudo systemctl status redis
# or
redis-cli ping

# Start Redis
sudo systemctl start redis
```

### "No module named 'zk'"

```bash
# Reinstall pyzk
pip install --upgrade pyzk
```

### Can't connect to device

1. Ping the device:
   ```bash
   ping 192.168.1.100
   ```

2. Check device is powered on

3. Verify IP address is correct

4. Check firewall rules

5. Ensure device and server are on same network

### CRM sync fails

1. Verify CRM_API_URL is correct (include trailing slash)
2. Verify CRM_API_TOKEN is valid
3. Check CRM endpoint accepts POST requests
4. Test with curl:
   ```bash
   curl -X POST \
     -H "Authorization: Token YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"user_id":"TEST","date":"2025-01-01"}' \
     https://your-crm.com/api/attendance/
   ```

## Next Steps

1. **Configure Celery Beat Schedule**
   - Go to Django Admin → Periodic Tasks
   - Adjust schedules as needed

2. **Set up Logging**
   - Check `logs/attendance_bridge.log`
   - Configure log rotation

3. **Add More Devices**
   - Add all your ZKTeco devices in admin

4. **Monitor Operations**
   - Check admin for attendance records
   - Monitor Celery logs
   - Check CRM for synced data

5. **Production Deployment**
   - Set DEBUG=False
   - Use Gunicorn/uWSGI
   - Set up Nginx
   - Configure Supervisor/systemd
   - Set up SSL/TLS

## Maintenance Commands

```bash
# View sync statistics
python manage.py test_crm --stats

# Retry failed syncs
python manage.py sync_to_crm --retry-failed

# Process specific date range
python manage.py process_attendance --start-date 2025-01-01 --end-date 2025-01-31

# Sync specific user
python manage.py sync_to_crm --user-id EMP001

# Test all devices
python manage.py test_device --all
```

## Getting Help

- Check README.md for detailed documentation
- Check logs in `logs/attendance_bridge.log`
- Use Django shell for debugging:
  ```bash
  python manage.py shell
  ```
