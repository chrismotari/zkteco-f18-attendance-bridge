"""
Serializers for REST API.
"""
from rest_framework import serializers
from .models import Device, RawAttendance, ProcessedAttendance
from attendance_bridge import settings
import pytz


class DeviceSerializer(serializers.ModelSerializer):
    """Serializer for Device model."""
    
    class Meta:
        model = Device
        fields = [
            'id', 'name', 'ip_address', 'port', 'enabled',
            'last_sync', 'created_at', 'updated_at'
        ]
        read_only_fields = ['last_sync', 'created_at', 'updated_at']


class RawAttendanceSerializer(serializers.ModelSerializer):
    """Serializer for RawAttendance model."""
    
    device_name = serializers.CharField(source='device.name', read_only=True)
    
    class Meta:
        model = RawAttendance
        fields = [
            'id', 'device', 'device_name', 'user_id', 'timestamp',
            'status', 'punch_state', 'verify_type', 'created_at'
        ]
        read_only_fields = ['created_at']


class ProcessedAttendanceSerializer(serializers.ModelSerializer):
    """Serializer for ProcessedAttendance model."""
    clock_in_local = serializers.SerializerMethodField()
    clock_out_local = serializers.SerializerMethodField()
    
    device_name = serializers.CharField(source='device.name', read_only=True)
    
    class Meta:
        model = ProcessedAttendance
        fields = [
            'id', 'device', 'device_name', 'user_id', 'date',
            'clock_in', 'clock_out', 'is_outlier', 'outlier_reason',
            'synced_to_crm', 'sync_attempts', 'last_sync_attempt',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'synced_to_crm', 'sync_attempts', 'last_sync_attempt',
            'created_at', 'updated_at'
        ]

    
    def get_clock_in_local(self, obj):
        """Return clock_in in user's timezone"""
        if not obj.clock_in:
            return None
        request = self.context.get('request')
        if request and hasattr(request, 'user_timezone'):
            tz = pytz.timezone(request.user_timezone)
        else:
            tz = pytz.timezone(settings.DISPLAY_TIMEZONE)
        return obj.clock_in.astimezone(tz).isoformat()

    def get_clock_out_local(self, obj):
        """Return clock_out in user's timezone"""
        if not obj.clock_out:
            return None
        request = self.context.get('request')
        if request and hasattr(request, 'user_timezone'):
            tz = pytz.timezone(request.user_timezone)
        else:
            tz = pytz.timezone(settings.DISPLAY_TIMEZONE)
        return obj.clock_out.astimezone(tz).isoformat()