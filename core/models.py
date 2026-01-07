"""
Django models for attendance bridge application.

This module defines the database models for:
- Device: ZKTeco attendance devices
- RawAttendance: Raw attendance logs from devices
- ProcessedAttendance: Processed attendance records with clock-in/out
"""
from django.db import models
from django.utils import timezone


class Device(models.Model):
    """
    Represents a ZKTeco attendance device.
    
    Attributes:
        name: Human-readable device name
        ip_address: IP address of the device
        port: TCP port for device communication (default 4370)
        enabled: Whether the device is active for polling
        last_sync: Timestamp of last successful sync
        created_at: Record creation timestamp
        updated_at: Record update timestamp
    """
    name = models.CharField(max_length=100, unique=True, help_text="Device name")
    ip_address = models.GenericIPAddressField(help_text="Device IP address")
    secondary_ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="Secondary IP address (failover)")
    port = models.IntegerField(default=4370, help_text="Device port (default 4370)")
    enabled = models.BooleanField(default=True, help_text="Is device enabled for polling")
    last_sync = models.DateTimeField(null=True, blank=True, help_text="Last successful sync timestamp")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Device'
        verbose_name_plural = 'Devices'

    def __str__(self):
        return f"{self.name} ({self.ip_address})"

    def update_last_sync(self):
        """Update the last_sync timestamp to now."""
        self.last_sync = timezone.now()
        self.save(update_fields=['last_sync'])


class User(models.Model):
    """
    Represents a user/employee from ZKTeco device.
    
    Attributes:
        user_id: User ID from the device (employee ID)
        name: User's full name
        privilege: User privilege level
        password: User password (if any)
        group_id: User group ID
        card_no: Card number
        device: Device this user was synced from
        created_at: Record creation timestamp
        updated_at: Record update timestamp
    """
    user_id = models.CharField(max_length=50, unique=True, db_index=True, help_text="User/Employee ID from device")
    name = models.CharField(max_length=100, help_text="User's full name")
    privilege = models.IntegerField(default=0, help_text="User privilege level")
    password = models.CharField(max_length=50, blank=True, help_text="User password")
    group_id = models.CharField(max_length=50, blank=True, help_text="User group ID")
    card_no = models.CharField(max_length=50, blank=True, help_text="Card number")
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='users', help_text="Source device")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user_id']
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.name} ({self.user_id})"


class RawAttendance(models.Model):
    """
    Stores raw attendance logs fetched from ZKTeco devices.
    
    Attributes:
        device: Foreign key to Device
        user_id: User ID from the device (employee ID)
        timestamp: Punch timestamp from device
        status: Punch status (0=check-in, 1=check-out, etc.)
        punch_state: Additional state information
        verify_type: Verification type (fingerprint, card, etc.)
        created_at: Record creation timestamp
    """
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='raw_attendances')
    user_id = models.CharField(max_length=50, db_index=True, help_text="User/Employee ID from device")
    timestamp = models.DateTimeField(db_index=True, help_text="Punch timestamp")
    status = models.IntegerField(help_text="Punch status code")
    punch_state = models.IntegerField(default=0, help_text="Punch state")
    verify_type = models.IntegerField(default=0, help_text="Verification type")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Raw Attendance'
        verbose_name_plural = 'Raw Attendances'
        # Unique constraint to avoid duplicate records
        unique_together = ['device', 'user_id', 'timestamp']
        indexes = [
            models.Index(fields=['user_id', 'timestamp']),
            models.Index(fields=['device', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.user_id} @ {self.timestamp} (Device: {self.device.name})"


class ProcessedAttendance(models.Model):
    """
    Stores processed attendance records with clock-in and clock-out times.
    
    This model represents the daily attendance summary for each user,
    containing the first punch (clock-in) and last punch (clock-out) of the day.
    
    Attributes:
        device: Foreign key to Device
        user_id: User/Employee ID
        date: Date of attendance (date only, no time)
        clock_in: Earliest punch timestamp for the day
        clock_out: Latest punch timestamp for the day
        is_outlier: Flag indicating if punches are outside normal work hours
        outlier_reason: Description of why it's flagged as outlier
        synced_to_crm: Whether this record has been synced to CRM
        sync_attempts: Number of sync attempts
        last_sync_attempt: Timestamp of last sync attempt
        created_at: Record creation timestamp
        updated_at: Record update timestamp
    """
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='processed_attendances')
    user_id = models.CharField(max_length=50, db_index=True, help_text="User/Employee ID")
    date = models.DateField(db_index=True, help_text="Attendance date")
    clock_in = models.DateTimeField(null=True, blank=True, help_text="Clock-in timestamp (earliest punch)")
    clock_out = models.DateTimeField(null=True, blank=True, help_text="Clock-out timestamp (latest punch)")
    is_outlier = models.BooleanField(default=False, help_text="Flagged as outlier")
    outlier_reason = models.TextField(blank=True, help_text="Reason for outlier flag")
    synced_to_crm = models.BooleanField(default=False, help_text="Synced to CRM")
    sync_attempts = models.IntegerField(default=0, help_text="Number of sync attempts")
    last_sync_attempt = models.DateTimeField(null=True, blank=True, help_text="Last sync attempt timestamp")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', 'user_id']
        verbose_name = 'Processed Attendance'
        verbose_name_plural = 'Processed Attendances'
        # One processed record per user per day per device
        unique_together = ['device', 'user_id', 'date']
        indexes = [
            models.Index(fields=['user_id', 'date']),
            models.Index(fields=['date', 'synced_to_crm']),
            models.Index(fields=['synced_to_crm', 'sync_attempts']),
        ]

    def __str__(self):
        return f"{self.user_id} on {self.date} (Device: {self.device.name})"

    @property
    def user_name(self):
        """Get the user's name from the User model."""
        try:
            user = User.objects.get(user_id=self.user_id)
            return user.name
        except User.DoesNotExist:
            return self.user_id  # Fallback to user_id if name not found

    @property
    def hours_worked(self):
        """Calculate hours worked based on clock-in and clock-out times."""
        if self.clock_in and self.clock_out:
            delta = self.clock_out - self.clock_in
            return round(delta.total_seconds() / 3600, 2)
        return None

    def mark_synced(self):
        """Mark this record as successfully synced to CRM."""
        self.synced_to_crm = True
        self.last_sync_attempt = timezone.now()
        self.save(update_fields=['synced_to_crm', 'last_sync_attempt', 'updated_at'])

    def increment_sync_attempts(self):
        """Increment sync attempt counter."""
        self.sync_attempts += 1
        self.last_sync_attempt = timezone.now()
        self.save(update_fields=['sync_attempts', 'last_sync_attempt', 'updated_at'])
