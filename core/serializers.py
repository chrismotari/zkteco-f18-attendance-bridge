"""
Serializers for REST API.
"""
from rest_framework import serializers
from .models import Device, RawAttendance, ProcessedAttendance


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
