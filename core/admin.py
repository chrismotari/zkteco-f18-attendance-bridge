"""
Django admin configuration for attendance bridge models.
"""
from django.contrib import admin
from .models import Device, RawAttendance, ProcessedAttendance, DeviceUser


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    """Admin interface for Device model."""
    list_display = ['name', 'ip_address', 'secondary_ip_address', 'port', 'enabled', 'last_sync', 'created_at']
    list_filter = ['enabled', 'created_at']
    search_fields = ['name', 'ip_address', 'secondary_ip_address']
    readonly_fields = ['created_at', 'updated_at', 'last_sync']
    fieldsets = (
        ('Device Information', {
            'fields': ('name', 'ip_address', 'secondary_ip_address', 'port', 'timezone', 'enabled')
        }),
        ('Sync Information', {
            'fields': ('last_sync',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DeviceUser)
class DeviceUserAdmin(admin.ModelAdmin):
    """Admin interface for DeviceUser model."""
    list_display = ['user_id', 'name', 'device', 'card_no', 'privilege', 'created_at']
    list_filter = ['device', 'privilege', 'created_at']
    search_fields = ['user_id', 'name', 'card_no']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('User Information', {
            'fields': ('user_id', 'name', 'device', 'privilege')
        }),
        ('Additional Info', {
            'fields': ('card_no', 'group_id', 'password')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(RawAttendance)
class RawAttendanceAdmin(admin.ModelAdmin):
    """Admin interface for RawAttendance model."""
    list_display = ['user_id', 'timestamp', 'device', 'status', 'created_at']
    list_filter = ['device', 'status', 'timestamp', 'created_at']
    search_fields = ['user_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'timestamp'
    fieldsets = (
        ('Attendance Information', {
            'fields': ('device', 'user_id', 'timestamp', 'status', 'punch_state', 'verify_type')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )


@admin.register(ProcessedAttendance)
class ProcessedAttendanceAdmin(admin.ModelAdmin):
    """Admin interface for ProcessedAttendance model."""
    list_display = ['user_id', 'date', 'clock_in', 'clock_out', 'is_late_arrival', 'is_early_departure', 'is_outlier', 'synced_to_crm', 'device']
    list_filter = ['is_late_arrival', 'is_early_departure', 'is_outlier', 'synced_to_crm', 'device', 'date']
    search_fields = ['user_id']
    readonly_fields = ['created_at', 'updated_at', 'last_sync_attempt']
    date_hierarchy = 'date'
    fieldsets = (
        ('Attendance Information', {
            'fields': ('device', 'user_id', 'date', 'clock_in', 'clock_out')
        }),
        ('Flags', {
            'fields': ('is_late_arrival', 'is_early_departure', 'is_outlier', 'outlier_reason')
        }),
        ('Sync Information', {
            'fields': ('synced_to_crm', 'sync_attempts', 'last_sync_attempt')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['mark_as_synced', 'mark_as_unsynced']

    def mark_as_synced(self, request, queryset):
        """Mark selected records as synced."""
        updated = queryset.update(synced_to_crm=True)
        self.message_user(request, f"{updated} records marked as synced.")
    mark_as_synced.short_description = "Mark as synced to CRM"

    def mark_as_unsynced(self, request, queryset):
        """Mark selected records as not synced."""
        updated = queryset.update(synced_to_crm=False)
        self.message_user(request, f"{updated} records marked as not synced.")
    mark_as_unsynced.short_description = "Mark as not synced to CRM"
