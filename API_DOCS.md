"""
API Documentation

This document describes the REST API endpoints available in the Attendance Bridge application.

## Authentication

All API endpoints require authentication. Use one of:

1. **Session Authentication** (for browser-based access)
2. **Token Authentication** (for programmatic access)

To create a token:
```python
python manage.py shell
>>> from django.contrib.auth.models import User
>>> from rest_framework.authtoken.models import Token
>>> user = User.objects.get(username='admin')
>>> token = Token.objects.create(user=user)
>>> print(token.key)
```

Use the token in requests:
```bash
curl -H "Authorization: Token YOUR_TOKEN_HERE" http://localhost:8000/api/devices/
```

## Base URL

```
http://localhost:8000/api/
```

## Endpoints

### Devices

#### List Devices
```
GET /api/devices/
```

Response:
```json
[
  {
    "id": 1,
    "name": "Main Office",
    "ip_address": "192.168.1.100",
    "port": 4370,
    "enabled": true,
    "last_sync": "2025-11-11T10:30:00Z",
    "created_at": "2025-11-01T08:00:00Z",
    "updated_at": "2025-11-11T10:30:00Z"
  }
]
```

#### Create Device
```
POST /api/devices/
Content-Type: application/json

{
  "name": "Branch Office",
  "ip_address": "192.168.1.101",
  "port": 4370,
  "enabled": true
}
```

#### Get Device Info (from device)
```
GET /api/devices/{id}/info/
```

Response:
```json
{
  "device_name": "Main Office",
  "ip_address": "192.168.1.100",
  "port": 4370,
  "firmware_version": "Ver 6.60",
  "serial_number": "DGD9190019050335134",
  "platform": "ZEM560",
  "user_count": 150,
  "attendance_count": 1250,
  "connected": true
}
```

#### Poll Device
```
POST /api/devices/{id}/poll/
```

Response:
```json
{
  "status": "success",
  "total_fetched": 120,
  "new_records": 15,
  "device": "Main Office"
}
```

#### Poll All Devices
```
POST /api/devices/poll_all/
```

Response:
```json
{
  "total_devices": 3,
  "successful": 3,
  "failed": 0,
  "devices": [
    {
      "device": "Main Office",
      "status": "success",
      "total_fetched": 120,
      "new_records": 15,
      "last_sync": "2025-11-11T10:30:00Z"
    }
  ]
}
```

### Raw Attendance

#### List Raw Attendance
```
GET /api/raw-attendance/
GET /api/raw-attendance/?user_id=EMP001
GET /api/raw-attendance/?device=1
GET /api/raw-attendance/?start_date=2025-11-01&end_date=2025-11-11
```

Response:
```json
{
  "count": 250,
  "next": "http://localhost:8000/api/raw-attendance/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "device": 1,
      "device_name": "Main Office",
      "user_id": "EMP001",
      "timestamp": "2025-11-11T08:15:30Z",
      "status": 0,
      "punch_state": 0,
      "verify_type": 1,
      "created_at": "2025-11-11T10:30:00Z"
    }
  ]
}
```

### Processed Attendance

#### List Processed Attendance
```
GET /api/processed-attendance/
GET /api/processed-attendance/?user_id=EMP001
GET /api/processed-attendance/?start_date=2025-11-01&end_date=2025-11-11
GET /api/processed-attendance/?is_outlier=true
GET /api/processed-attendance/?synced_to_crm=false
```

Response:
```json
{
  "count": 50,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "device": 1,
      "device_name": "Main Office",
      "user_id": "EMP001",
      "date": "2025-11-11",
      "clock_in": "2025-11-11T08:15:30Z",
      "clock_out": "2025-11-11T17:30:00Z",
      "is_outlier": false,
      "outlier_reason": "",
      "synced_to_crm": true,
      "sync_attempts": 1,
      "last_sync_attempt": "2025-11-11T11:00:00Z",
      "created_at": "2025-11-11T10:30:00Z",
      "updated_at": "2025-11-11T11:00:00Z"
    }
  ]
}
```

#### Get Unsynced Records
```
GET /api/processed-attendance/unsynced/
GET /api/processed-attendance/unsynced/?limit=50
```

#### Get Outliers
```
GET /api/processed-attendance/outliers/
```

#### Get Sync Statistics
```
GET /api/processed-attendance/stats/
```

Response:
```json
{
  "total": 500,
  "synced": 480,
  "unsynced": 20,
  "failed": 2,
  "sync_percentage": 96.0
}
```

#### Trigger Processing
```
POST /api/processed-attendance/process/
```

Response:
```json
{
  "total_records": 150,
  "processed": 145,
  "outliers": 12,
  "failed": 5
}
```

#### Trigger CRM Sync
```
POST /api/processed-attendance/sync/?limit=100
```

Response:
```json
{
  "total": 50,
  "successful": 48,
  "failed": 2,
  "errors": [
    {
      "user_id": "EMP001",
      "date": "2025-11-10",
      "error": "Connection timeout"
    }
  ]
}
```

## Query Parameters

### Pagination
- `page` - Page number (default: 1)
- `page_size` - Results per page (default: 100)

### Filtering
- `user_id` - Filter by user ID
- `device` - Filter by device ID
- `start_date` - Filter from date (YYYY-MM-DD)
- `end_date` - Filter to date (YYYY-MM-DD)
- `is_outlier` - Filter outliers (true/false)
- `synced_to_crm` - Filter sync status (true/false)

### Ordering
- `ordering` - Order by field (prefix with - for descending)
  - Examples: `ordering=date`, `ordering=-timestamp`

## Error Responses

### 400 Bad Request
```json
{
  "error": "Invalid date format"
}
```

### 401 Unauthorized
```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 404 Not Found
```json
{
  "detail": "Not found."
}
```

### 503 Service Unavailable
```json
{
  "error": "Failed to connect to device"
}
```

## Examples

### Python (requests)

```python
import requests

API_URL = "http://localhost:8000/api/"
TOKEN = "your-token-here"

headers = {
    "Authorization": f"Token {TOKEN}",
    "Content-Type": "application/json"
}

# Get unsynced attendance
response = requests.get(
    f"{API_URL}processed-attendance/unsynced/",
    headers=headers
)
data = response.json()

# Poll devices
response = requests.post(
    f"{API_URL}devices/poll_all/",
    headers=headers
)
result = response.json()
print(f"Polled {result['total_devices']} devices")
```

### JavaScript (fetch)

```javascript
const API_URL = 'http://localhost:8000/api/';
const TOKEN = 'your-token-here';

const headers = {
    'Authorization': `Token ${TOKEN}`,
    'Content-Type': 'application/json'
};

// Get processed attendance
fetch(`${API_URL}processed-attendance/?user_id=EMP001`, {
    headers: headers
})
.then(response => response.json())
.then(data => console.log(data));

// Trigger sync
fetch(`${API_URL}processed-attendance/sync/`, {
    method: 'POST',
    headers: headers
})
.then(response => response.json())
.then(data => console.log(`Synced ${data.successful} records`));
```

### curl

```bash
# Get devices
curl -H "Authorization: Token YOUR_TOKEN" \
  http://localhost:8000/api/devices/

# Poll all devices
curl -X POST -H "Authorization: Token YOUR_TOKEN" \
  http://localhost:8000/api/devices/poll_all/

# Get unsynced attendance
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/api/processed-attendance/unsynced/?limit=10"

# Trigger sync
curl -X POST -H "Authorization: Token YOUR_TOKEN" \
  http://localhost:8000/api/processed-attendance/sync/
```
