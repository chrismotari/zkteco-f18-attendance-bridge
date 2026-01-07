"""
Device polling utilities for ZKTeco F18 attendance devices.

This module provides functions to:
- Connect to ZKTeco devices using pyzk library
- Fetch attendance logs from devices
- Store raw attendance data in the database
- Handle connection errors and timeouts
"""
import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from zk import ZK
from django.conf import settings
from django.utils import timezone
import pytz
from .models import Device, RawAttendance

logger = logging.getLogger('core')


def connect_device(device_or_ip, port=4370, timeout=5):
    """
    Connect to a ZKTeco device.
    
    Args:
        device_or_ip: Either a Device model instance or IP address string
        port: Device port (only used if device_or_ip is an IP address)
        timeout: Connection timeout in seconds
    
    Returns:
        Connected ZK instance or None
    """
    # Handle both Device objects and IP addresses
    if isinstance(device_or_ip, Device):
        ip_address = device_or_ip.ip_address
        secondary_ip = device_or_ip.secondary_ip_address
        port = device_or_ip.port
        device_name = device_or_ip.name
    else:
        ip_address = device_or_ip
        secondary_ip = None
        device_name = ip_address
    
    try:
        # Try with device key and communication key
        connection_attempts = [
            {'password': 1, 'force_udp': True, 'ommit_ping': True},
            {'password': 1, 'force_udp': False, 'ommit_ping': True},
            {'password': 0, 'force_udp': True, 'ommit_ping': True},
            {'password': 0, 'force_udp': False, 'ommit_ping': True},
        ]
        
        last_error = None
        ip_addresses_to_try = [ip_address]
        if secondary_ip:
            ip_addresses_to_try.append(secondary_ip)
        
        for current_ip in ip_addresses_to_try:
            ip_label = "primary" if current_ip == ip_address else "secondary"
            for attempt in connection_attempts:
                try:
                    logger.info(f"Trying {ip_label} connection to {device_name} ({current_ip}):4370 (Password={attempt['password']}, UDP={attempt['force_udp']})")
                    zk = ZK(current_ip, port=port, timeout=timeout, **attempt)
                    conn = zk.connect()
                    logger.info(f"Successfully connected to {device_name} ({current_ip}):{port} via {ip_label} IP")
                    return conn
                except Exception as e:
                    last_error = e
                    continue
            
            logger.warning(f"Failed to connect to {device_name} via {ip_label} IP ({current_ip})")
        
        # If all attempts failed, raise the last error
        raise last_error if last_error else Exception("Connection failed to all IP addresses")
        
    except Exception as e:
        logger.error(f"Failed to connect to device at {device_name} ({ip_address}):{port}: {str(e)}")
        raise


def fetch_attendance(device: Device, since: datetime = None, timeout: int = None) -> Tuple[int, int]:
    """
    Fetch attendance logs from a ZKTeco device and store them in the database.
    
    Args:
        device: Device model instance
        since: Only fetch records after this datetime (optional)
    
    Returns:
        Tuple of (total_fetched, new_records_created)
    """
    # Allow caller to override connect timeout for large datasets/devices
    if timeout is not None:
        conn = connect_device(device, timeout=timeout)
    else:
        conn = connect_device(device)
    if not conn:
        return 0, 0
    
    total_fetched = 0
    new_records = 0
    
    try:
        # Disable device to prevent new punches during sync
        conn.disable_device()
        logger.info(f"Device {device.name} disabled for sync")
        
        # Fetch attendance logs
        attendances = conn.get_attendance()
        total_fetched = len(attendances)
        logger.info(f"Fetched {total_fetched} attendance records from {device.name}")
        
        # Process and store each attendance record
        for attendance in attendances:
            # Determine device timezone. Prefer a `timezone` attribute on Device,
            # then settings.DEVICE_TIME_ZONE, and finally fall back to Africa/Nairobi (EAT).
            device_tz_name = getattr(device, 'timezone', None) or getattr(settings, 'DEVICE_TIME_ZONE', None) or 'Africa/Nairobi'
            try:
                device_tz = pytz.timezone(device_tz_name)
            except Exception:
                device_tz = pytz.UTC

            # Convert the attendance timestamp to an aware UTC datetime before comparing/storing.
            att_ts = attendance.timestamp
            if timezone.is_naive(att_ts):
                # Localize naive timestamp as device-local time
                local_dt = device_tz.localize(att_ts)
            else:
                local_dt = att_ts

            utc_ts = local_dt.astimezone(pytz.UTC)

            # If a 'since' filter is provided, normalize it to UTC for comparison
            if since:
                if timezone.is_naive(since):
                    try:
                        settings_tz = pytz.timezone(settings.TIME_ZONE)
                    except Exception:
                        settings_tz = pytz.UTC
                    since_aware = settings_tz.localize(since).astimezone(pytz.UTC)
                else:
                    since_aware = since.astimezone(pytz.UTC)

                if utc_ts < since_aware:
                    continue

            # Use get_or_create to avoid duplicates. Store UTC-aware timestamp.
            obj, created = RawAttendance.objects.get_or_create(
                device=device,
                user_id=str(attendance.user_id),
                timestamp=utc_ts,
                defaults={
                    'status': attendance.status,
                    'punch_state': getattr(attendance, 'punch', 0),
                    'verify_type': getattr(attendance, 'verify_type', 0),
                }
            )
            
            if created:
                new_records += 1
                logger.debug(f"Created new attendance record: {obj}")
        
        logger.info(f"Stored {new_records} new records from {device.name} (total fetched: {total_fetched})")
        
        # Update device last_sync timestamp
        device.update_last_sync()
        
    except Exception as e:
        logger.error(f"Error fetching attendance from {device.name}: {str(e)}")
        raise
    finally:
        # Re-enable device and disconnect
        try:
            conn.enable_device()
            logger.info(f"Device {device.name} re-enabled")
        except Exception as e:
            logger.warning(f"Failed to re-enable device {device.name}: {str(e)}")
        
        try:
            conn.disconnect()
            logger.info(f"Disconnected from {device.name}")
        except Exception as e:
            logger.warning(f"Error disconnecting from {device.name}: {str(e)}")
    
    return total_fetched, new_records


def poll_all_devices(since: datetime = None) -> dict:
    """
    Poll all enabled devices and fetch their attendance logs.
    
    Args:
        since: Only fetch records after this datetime (optional)
    
    Returns:
        Dictionary with polling results for each device
    """
    devices = Device.objects.filter(enabled=True)
    results = {
        'total_devices': devices.count(),
        'successful': 0,
        'failed': 0,
        'devices': []
    }
    
    logger.info(f"Starting polling for {results['total_devices']} enabled devices")
    
    for device in devices:
        try:
            total_fetched, new_records = fetch_attendance(device, since=since)
            results['successful'] += 1
            results['devices'].append({
                'device': device.name,
                'status': 'success',
                'total_fetched': total_fetched,
                'new_records': new_records,
                'last_sync': device.last_sync
            })
        except Exception as e:
            results['failed'] += 1
            results['devices'].append({
                'device': device.name,
                'status': 'failed',
                'error': str(e)
            })
            logger.error(f"Failed to poll device {device.name}: {str(e)}")
    
    logger.info(f"Polling complete: {results['successful']} successful, {results['failed']} failed")
    return results


def get_device_info(device: Device) -> Optional[dict]:
    """
    Get information from a ZKTeco device.
    
    Args:
        device: Device model instance
    
    Returns:
        Dictionary with device information or None if connection fails
    """
    conn = connect_device(device.ip_address, device.port)
    if not conn:
        return None
    
    try:
        info = {
            'device_name': device.name,
            'ip_address': device.ip_address,
            'port': device.port,
            'firmware_version': conn.get_firmware_version(),
            'serial_number': conn.get_serialnumber(),
            'platform': conn.get_platform(),
            'device_name_internal': conn.get_device_name(),
            'user_count': len(conn.get_users()),
            'attendance_count': len(conn.get_attendance()),
            'connected': True
        }
        logger.info(f"Retrieved info from device {device.name}")
        return info
    except Exception as e:
        logger.error(f"Error getting info from device {device.name}: {str(e)}")
        return None
    finally:
        try:
            conn.disconnect()
        except:
            pass


def test_device_connection(ip_address, port=4370):
    """
    Test connection to a device and print device information.
    """
    # Try different connection methods with device password
    connection_attempts = [
        {'password': 1, 'force_udp': True, 'ommit_ping': True},
        {'password': 1, 'force_udp': False, 'ommit_ping': True},
        {'password': 0, 'force_udp': True, 'ommit_ping': True},
        {'password': 0, 'force_udp': False, 'ommit_ping': True},
    ]
    
    last_error = None
    for attempt in connection_attempts:
        try:
            logger.info(f"Testing connection to {ip_address}:{port} (Password={attempt['password']}, UDP={attempt['force_udp']})")
            zk = ZK(ip_address, port=port, timeout=5, **attempt)
            conn = zk.connect()
            
            # Get device info
            firmware = conn.get_firmware_version()
            serial = conn.get_serialnumber()
            platform = conn.get_platform()
            device_name = conn.get_device_name()
            
            logger.info(f"✓ Connection successful!")
            logger.info(f"  Firmware: {firmware}")
            logger.info(f"  Serial: {serial}")
            logger.info(f"  Platform: {platform}")
            logger.info(f"  Device Name: {device_name}")
            
            # Get user and attendance count
            users = conn.get_users()
            logger.info(f"  Registered Users: {len(users)}")
            
            attendance = conn.get_attendance()
            logger.info(f"  Attendance Records: {len(attendance)}")
            
            conn.disconnect()
            return True
            
        except Exception as e:
            last_error = e
            continue
    
    logger.error(f"Connection failed after all attempts. Check device password, IP, and network connectivity.")
    logger.error(f"Last error: {str(last_error)}")
    return False


def clear_device_attendance(device: Device) -> bool:
    """
    Clear all attendance records from a device.
    WARNING: This is destructive and should be used with caution.
    
    Args:
        device: Device model instance
    
    Returns:
        True if successful, False otherwise
    """
    conn = connect_device(device)
    if not conn:
        return False
    
    try:
        conn.disable_device()
        conn.clear_attendance()
        logger.warning(f"Cleared all attendance records from device {device.name}")
        conn.enable_device()
        return True
    except Exception as e:
        logger.error(f"Error clearing attendance from device {device.name}: {str(e)}")
        return False
    finally:
        try:
            conn.disconnect()
        except:
            pass


def get_device_users(device: Device) -> list:
    """
    Get all users from a device.
    
    Args:
        device: Device model instance
    
    Returns:
        List of user dictionaries with user info
    """
    conn = connect_device(device)
    if not conn:
        return []
    
    try:
        users = conn.get_users()
        user_list = []
        
        for user in users:
            user_list.append({
                'user_id': str(user.user_id),
                'name': user.name or f"User {user.user_id}",
                'privilege': user.privilege,
                'password': user.password or '',
                'group_id': str(user.group_id) if hasattr(user, 'group_id') else '',
                'card_no': str(user.card_no) if hasattr(user, 'card_no') else '',
            })
        
        return user_list
    except Exception as e:
        logger.error(f"Error getting users from device {device.name}: {str(e)}")
        return []
    finally:
        try:
            conn.disconnect()
        except:
            pass


def delete_device_user(device: Device, user_id: str) -> bool:
    """
    Delete a user from a device.
    
    Args:
        device: Device model instance
        user_id: User ID to delete
    
    Returns:
        True if successful, False otherwise
    """
    conn = connect_device(device)
    if not conn:
        return False
    
    try:
        conn.disable_device()
        
        # pyzk's delete_user requires uid as integer, but it has a 16-bit limit
        # For user_ids that are too large, we need to use the user_id string directly
        try:
            uid_int = int(user_id)
            # Check if within 16-bit signed integer range (-32768 to 32767)
            if -32768 <= uid_int <= 32767:
                conn.delete_user(uid=uid_int)
            else:
                # For large user IDs, try deleting by user_id string
                conn.delete_user(user_id=user_id)
        except (ValueError, TypeError):
            # If user_id is not a valid integer, try as string
            conn.delete_user(user_id=user_id)
        
        logger.info(f"Deleted user {user_id} from device {device.name}")
        conn.enable_device()
        return True
    except Exception as e:
        logger.error(f"Error deleting user {user_id} from device {device.name}: {str(e)}")
        return False
    finally:
        try:
            conn.enable_device()
        except:
            pass
        try:
            conn.disconnect()
        except:
            pass


def sync_device_users_to_db(device: Device) -> dict:
    """
    Sync users from device to database.
    
    Args:
        device: Device model instance
    
    Returns:
        Dictionary with sync results
    """
    from .models import DeviceUser
    
    conn = connect_device(device)
    if not conn:
        return {'success': False, 'error': 'Failed to connect to device'}
    
    try:
        users = conn.get_users()
        created_count = 0
        updated_count = 0
        
        for user in users:
            user_obj, created = DeviceUser.objects.update_or_create(
                user_id=str(user.user_id),
                defaults={
                    'name': user.name or f"User {user.user_id}",
                    'privilege': user.privilege,
                    'password': user.password or '',
                    'group_id': str(user.group_id) if hasattr(user, 'group_id') else '',
                    'card_no': str(user.card_no) if hasattr(user, 'card_no') else '',
                    'device': device,
                }
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1
        
        return {
            'success': True,
            'total': len(users),
            'created': created_count,
            'updated': updated_count
        }
    except Exception as e:
        logger.error(f"Error syncing users from device {device.name}: {str(e)}")
        return {'success': False, 'error': str(e)}
    finally:
        try:
            conn.disconnect()
        except:
            pass
