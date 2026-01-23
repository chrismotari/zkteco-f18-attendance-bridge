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
    timezone = models.CharField(max_length=50, default='Africa/Nairobi', help_text="Device timezone (e.g., Africa/Nairobi, UTC)")
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


class DeviceUser(models.Model):
    """
    Represents a user/employee from ZKTeco device.
    
    Attributes:
        user_id: User ID from the device (employee ID)
        name: User's name from device
        full_name: User's full name (optional, preferred for display)
        privilege: User privilege level
        password: User password (if any)
        group_id: User group ID
        card_no: Card number
        device: Device this user was synced from
        created_at: Record creation timestamp
        updated_at: Record update timestamp
    """
    user_id = models.CharField(max_length=50, unique=True, db_index=True, help_text="User/Employee ID from device")
    name = models.CharField(max_length=100, help_text="User's name from device")
    full_name = models.CharField(max_length=200, blank=True, help_text="User's full name (preferred for display)")
    privilege = models.IntegerField(default=0, help_text="User privilege level")
    password = models.CharField(max_length=50, blank=True, help_text="User password")
    group_id = models.CharField(max_length=50, blank=True, help_text="User group ID")
    card_no = models.CharField(max_length=50, blank=True, help_text="Card number")
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='device_users', help_text="Source device")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user_id']
        verbose_name = 'Device User'
        verbose_name_plural = 'Device Users'

    def __str__(self):
        return f"{self.display_name} ({self.user_id})"
    
    @property
    def display_name(self):
        """Return full_name if available, otherwise fall back to name."""
        return self.full_name if self.full_name else self.name


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
    Stores processed attendance records for shifts with punches WITHIN the shift window.
    
    Only contains punches that fall within the acceptable shift timeframe.
    Outlier punches (outside shift window) are stored separately in OutlierPunch.
    
    NEW FIELDS (Core Engine):
        shift_date: Date this shift belongs to (shift start date)
        shift_start_time: Expected shift start time (e.g., 20:00)
        shift_end_time: Expected shift end time (e.g., 05:00)
        earliest_punch: First punch within acceptable shift window
        latest_punch: Last punch within acceptable shift window
        punch_count: Number of punches within shift window
        
    LEGACY FIELDS (for backward compatibility during migration):
        date: Use shift_date instead
        clock_in: Use earliest_punch instead
        clock_out: Use latest_punch instead
        is_outlier: Outliers now in OutlierPunch table
        outlier_reason: Moved to OutlierPunch
    """
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='processed_attendances')
    user_id = models.CharField(max_length=50, db_index=True, help_text="User/Employee ID")
    
    # NEW CORE FIELDS
    shift_date = models.DateField(db_index=True, null=True, blank=True, help_text="Shift date (when shift starts)")
    shift_start_time = models.TimeField(null=True, blank=True, help_text="Expected shift start time")
    shift_end_time = models.TimeField(null=True, blank=True, help_text="Expected shift end time")
    earliest_punch = models.DateTimeField(null=True, blank=True, help_text="First punch within shift window")
    latest_punch = models.DateTimeField(null=True, blank=True, help_text="Last punch within shift window")
    punch_count = models.IntegerField(default=0, help_text="Number of punches within shift window")
    
    # FLAGS
    is_late_arrival = models.BooleanField(default=False, help_text="Punched in late")
    is_early_departure = models.BooleanField(default=False, help_text="Punched out early")
    is_incomplete = models.BooleanField(default=False, help_text="Missing punch within shift window")
    notes = models.TextField(blank=True, help_text="Additional notes")
    
    # LEGACY FIELDS (keep for backward compatibility)
    date = models.DateField(db_index=True, null=True, blank=True, help_text="LEGACY: use shift_date")
    clock_in = models.DateTimeField(null=True, blank=True, help_text="LEGACY: use earliest_punch")
    clock_out = models.DateTimeField(null=True, blank=True, help_text="LEGACY: use latest_punch")
    is_outlier = models.BooleanField(default=False, help_text="LEGACY: outliers now in OutlierPunch table")
    outlier_reason = models.TextField(blank=True, help_text="LEGACY: moved to OutlierPunch")
    
    # CRM SYNC
    synced_to_crm = models.BooleanField(default=False, help_text="Synced to CRM")
    sync_attempts = models.IntegerField(default=0, help_text="Number of sync attempts")
    last_sync_attempt = models.DateTimeField(null=True, blank=True, help_text="Last sync attempt timestamp")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-shift_date', 'user_id']
        verbose_name = 'Processed Attendance'
        verbose_name_plural = 'Processed Attendances'
        # One processed record per user per shift per device
        unique_together = ['device', 'user_id', 'shift_date']
        indexes = [
            models.Index(fields=['user_id', 'shift_date']),
            models.Index(fields=['shift_date', 'synced_to_crm']),
            models.Index(fields=['synced_to_crm', 'sync_attempts']),
            # Legacy indexes
            models.Index(fields=['user_id', 'date']),
            models.Index(fields=['date', 'synced_to_crm']),
        ]

    def __str__(self):
        return f"{self.user_id} on {self.shift_date or self.date} (Device: {self.device.name})"

    @property
    def user_name(self):
        """Get the user's name from the DeviceUser model."""
        try:
            user = DeviceUser.objects.get(user_id=self.user_id)
            return user.name
        except DeviceUser.DoesNotExist:
            return self.user_id  # Fallback to user_id if name not found

    @property
    def hours_worked(self):
        """Calculate hours worked based on earliest and latest punches."""
        punch_in = self.earliest_punch or self.clock_in
        punch_out = self.latest_punch or self.clock_out
        
        if punch_in and punch_out:
            delta = punch_out - punch_in
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


class OutlierPunch(models.Model):
    """
    Stores individual punch records that fall outside the acceptable shift window.
    
    Each outlier punch gets its own record. These are punches that cannot be 
    classified as part of a normal shift (e.g., punching at 2pm when shift is 8pm-5am).
    
    Attributes:
        device: Foreign key to Device
        user_id: User/Employee ID
        punch_datetime: The actual timestamp of the outlier punch
        reason: Why this punch is considered an outlier
        associated_shift_date: The shift date this might belong to (nullable)
        reviewed: Whether this outlier has been reviewed by admin
        notes: Admin notes about this outlier
        created_at: Record creation timestamp
    """
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='outlier_punches')
    user_id = models.CharField(max_length=50, db_index=True, help_text="User/Employee ID")
    punch_datetime = models.DateTimeField(db_index=True, help_text="Actual punch timestamp")
    reason = models.TextField(help_text="Why this is an outlier")
    associated_shift_date = models.DateField(null=True, blank=True, help_text="Potential shift date")
    reviewed = models.BooleanField(default=False, help_text="Has been reviewed by admin")
    notes = models.TextField(blank=True, help_text="Admin notes")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-punch_datetime']
        verbose_name = 'Outlier Punch'
        verbose_name_plural = 'Outlier Punches'
        unique_together = ['device', 'user_id', 'punch_datetime']
        indexes = [
            models.Index(fields=['user_id', 'punch_datetime']),
            models.Index(fields=['punch_datetime', 'reviewed']),
            models.Index(fields=['associated_shift_date']),
        ]
    
    def __str__(self):
        return f"{self.user_id} @ {self.punch_datetime} (Outlier)"
    
    @property
    def user_name(self):
        """Get the user's name from the DeviceUser model."""
        try:
            user = DeviceUser.objects.get(user_id=self.user_id)
            return user.name
        except DeviceUser.DoesNotExist:
            return self.user_id
