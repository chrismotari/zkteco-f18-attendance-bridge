"""
REST API views for attendance bridge.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import render
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Device, RawAttendance, ProcessedAttendance
from .serializers import DeviceSerializer, RawAttendanceSerializer, ProcessedAttendanceSerializer
from .device_utils import poll_all_devices, get_device_info
from .processing_utils import process_all_unprocessed_attendance, get_unsynced_attendance
from .crm_utils import sync_unsynced_attendance, get_sync_statistics
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .processing_utils import process_attendance_for_date


class DeviceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Device model.
    
    Provides CRUD operations and custom actions for device management.
    """
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=True, methods=['get'])
    def info(self, request, pk=None):
        """Get detailed information from a device."""
        device = self.get_object()
        info = get_device_info(device)
        
        if info:
            return Response(info)
        else:
            return Response(
                {'error': 'Failed to connect to device'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
    
    @action(detail=True, methods=['post'])
    def poll(self, request, pk=None):
        """Manually poll a specific device."""
        device = self.get_object()
        
        from .device_utils import fetch_attendance
        
        try:
            total_fetched, new_records = fetch_attendance(device)
            return Response({
                'status': 'success',
                'total_fetched': total_fetched,
                'new_records': new_records,
                'device': device.name
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
    
    @action(detail=False, methods=['post'])
    def poll_all(self, request):
        """Poll all enabled devices."""
        results = poll_all_devices()
        return Response(results)


class RawAttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for RawAttendance model (read-only).
    
    Provides listing and filtering of raw attendance records.
    """
    queryset = RawAttendance.objects.all()
    serializer_class = RawAttendanceSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['device', 'user_id', 'status']
    search_fields = ['user_id']
    ordering_fields = ['timestamp', 'created_at']
    ordering = ['-timestamp']
    
    def get_queryset(self):
        """Filter queryset based on query parameters."""
        queryset = super().get_queryset()
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        return queryset


class ProcessedAttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for ProcessedAttendance model (read-only).
    
    Provides listing and filtering of processed attendance records.
    """
    queryset = ProcessedAttendance.objects.all()
    serializer_class = ProcessedAttendanceSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['device', 'user_id', 'is_outlier', 'synced_to_crm']
    search_fields = ['user_id']
    ordering_fields = ['date', 'created_at']
    ordering = ['-date']
    
    def get_queryset(self):
        """Filter queryset based on query parameters."""
        queryset = super().get_queryset()
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def unsynced(self, request):
        """Get unsynced attendance records."""
        limit = int(request.query_params.get('limit', 100))
        records = get_unsynced_attendance(limit=limit)
        serializer = self.get_serializer(records, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def outliers(self, request):
        """Get attendance records flagged as outliers."""
        queryset = self.get_queryset().filter(is_outlier=True)
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def process(self, request):
        """Manually trigger processing of raw attendance."""
        results = process_all_unprocessed_attendance()
        return Response(results)
    
    @action(detail=False, methods=['post'])
    def sync(self, request):
        """Manually trigger sync to CRM."""
        limit = int(request.query_params.get('limit', 100))
        results = sync_unsynced_attendance(limit=limit)
        return Response(results)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get sync statistics."""
        stats = get_sync_statistics()
        return Response(stats)


# Web Views for HTML Templates
def attendance_report(request):
    """
    Display attendance report for a specific date.
    Allows filtering by date and device.
    """
    # Get date from request (default to today)
    selected_date_str = request.GET.get('date')
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = timezone.now().date()
    else:
        selected_date = timezone.now().date()
    
    # Get device filter
    device_id = request.GET.get('device')
    
    # Query processed attendance for selected date
    attendances = ProcessedAttendance.objects.filter(date=selected_date)
    
    # Apply device filter if specified
    if device_id:
        attendances = attendances.filter(device_id=device_id)
    
    # Order by user_id
    attendances = attendances.select_related('device').order_by('user_id')
    
    # Get all devices for filter dropdown
    devices = Device.objects.all()
    
    # Calculate statistics
    total_records = attendances.count()
    outliers_count = attendances.filter(is_outlier=True).count()
    normal_count = total_records - outliers_count
    synced_count = attendances.filter(synced_to_crm=True).count()
    unsynced_count = total_records - synced_count
    
    # Calculate total hours worked
    total_hours = 0
    for attendance in attendances:
        if attendance.clock_in and attendance.clock_out:
            hours = attendance.hours_worked
            if hours:
                total_hours += hours
    
    context = {
        'selected_date': selected_date,
        'selected_device_id': device_id,
        'attendances': attendances,
        'devices': devices,
        'statistics': {
            'total_records': total_records,
            'outliers_count': outliers_count,
            'normal_count': normal_count,
            'synced_count': synced_count,
            'unsynced_count': unsynced_count,
            'total_hours': round(total_hours, 2),
        },
        'prev_date': selected_date - timedelta(days=1),
        'next_date': selected_date + timedelta(days=1),
        'today': timezone.now().date(),
    }
    
    return render(request, 'core/attendance_report.html', context)


@require_POST
def delete_attendance(request):
    """
    Delete raw attendance records related to a processed attendance.

    This removes the RawAttendance rows from the bridge database and re-processes
    the attendance for that user/date. Note: ZKTeco devices (pyzk) generally do
    not support deleting a single attendance record remotely; only clearing all
    attendance logs is supported. This view only deletes records from the
    bridge DB. Use the device management actions to clear device logs if needed.
    """
    processed_id = request.POST.get('processed_id')
    delete_which = request.POST.get('which', 'both')  # 'in', 'out', or 'both'

    if not processed_id:
        return JsonResponse({'error': 'processed_id is required'}, status=400)

    try:
        processed = ProcessedAttendance.objects.select_related('device').get(id=processed_id)
    except ProcessedAttendance.DoesNotExist:
        return JsonResponse({'error': 'ProcessedAttendance not found'}, status=404)

    # Identify raw timestamps to delete
    to_delete = []
    if delete_which in ('in', 'both') and processed.clock_in:
        to_delete.append(processed.clock_in)
    if delete_which in ('out', 'both') and processed.clock_out:
        to_delete.append(processed.clock_out)

    deleted_count = 0
    for ts in to_delete:
        qs = RawAttendance.objects.filter(
            device=processed.device,
            user_id=processed.user_id,
            timestamp=ts
        )
        deleted_count += qs.count()
        qs.delete()

    # Re-process attendance for this user/date so processed record reflects deletion
    try:
        process_attendance_for_date(processed.user_id, processed.date, device=processed.device)
    except Exception as e:
        # Processing failure is not fatal for deletion, but report it
        return JsonResponse({'deleted': deleted_count, 'processing_error': str(e)})

    return JsonResponse({'deleted': deleted_count})


def attendance_print(request):
    """
    Print-friendly version of attendance report.
    """
    # Get date from request (default to today)
    selected_date_str = request.GET.get('date')
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = timezone.now().date()
    else:
        selected_date = timezone.now().date()
    
    # Get device filter
    device_id = request.GET.get('device')
    
    # Query processed attendance for selected date
    attendances = ProcessedAttendance.objects.filter(date=selected_date)
    
    # Apply device filter if specified
    selected_device = None
    if device_id:
        attendances = attendances.filter(device_id=device_id)
        try:
            selected_device = Device.objects.get(id=device_id).name
        except Device.DoesNotExist:
            pass
    
    # Order by user_id
    attendances = attendances.select_related('device').order_by('user_id')
    
    # Calculate statistics
    total_records = attendances.count()
    outliers_count = attendances.filter(is_outlier=True).count()
    normal_count = total_records - outliers_count
    synced_count = attendances.filter(synced_to_crm=True).count()
    unsynced_count = total_records - synced_count
    
    # Calculate total hours worked
    total_hours = 0
    for attendance in attendances:
        if attendance.clock_in and attendance.clock_out:
            hours = attendance.hours_worked
            if hours:
                total_hours += hours
    
    context = {
        'selected_date': selected_date,
        'selected_device': selected_device,
        'attendances': attendances,
        'statistics': {
            'total_records': total_records,
            'outliers_count': outliers_count,
            'normal_count': normal_count,
            'synced_count': synced_count,
            'unsynced_count': unsynced_count,
            'total_hours': round(total_hours, 2),
        },
        'now': timezone.now(),
    }
    
    return render(request, 'core/attendance_print.html', context)


def sync_day(request):
    """
    Sync attendance for a specific day: fetch raw data and process it.
    """
    from django.http import JsonResponse
    from django.views.decorators.http import require_POST
    from django.utils import timezone as tz
    from .device_utils import connect_device, fetch_attendance
    from .processing_utils import process_all_attendance_for_date
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST request required'}, status=405)
    
    # Get date from request
    date_str = request.POST.get('date')
    device_id = request.POST.get('device')
    
    if not date_str:
        return JsonResponse({'error': 'Date is required'}, status=400)
    
    try:
        sync_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
    
    # Get devices to sync
    if device_id:
        devices = Device.objects.filter(id=device_id, enabled=True)
    else:
        devices = Device.objects.filter(enabled=True)
    
    if not devices.exists():
        return JsonResponse({'error': 'No enabled devices found'}, status=404)
    
    results = {
        'date': date_str,
        'devices': [],
        'total_raw_fetched': 0,
        'total_processed': 0,
    }
    
    # Fetch raw attendance for each device
    for device in devices:
        device_result = {
            'name': device.name,
            'raw_fetched': 0,
            'processed': 0,
            'error': None,
        }
        
        try:
            # Check if we already have data for this date from this device
            existing_count = RawAttendance.objects.filter(
                device=device,
                timestamp__date=sync_date
            ).count()
            
            if existing_count > 0:
                # We already have data, just reprocess it
                device_result['raw_fetched'] = 0
                device_result['error'] = f"Using {existing_count} existing records (skipped fetch)"
            else:
                # Only fetch if we don't have data for this date
                from zk import ZK
                # Use shorter timeout to avoid hanging
                zk = ZK(device.ip_address, port=device.port, timeout=15, password=1, 
                       force_udp=True, ommit_ping=True)
                conn = zk.connect()
                
                # Get attendance records (this might timeout for large datasets)
                try:
                    attendances = conn.get_attendance()
                    
                    # Filter for the specific date and store
                    stored = 0
                    for att in attendances:
                        # Check if attendance is for the target date
                        if att.timestamp.date() == sync_date:
                            # Make timestamp timezone-aware
                            if att.timestamp.tzinfo is None:
                                aware_timestamp = tz.make_aware(att.timestamp)
                            else:
                                aware_timestamp = att.timestamp
                            
                            _, created = RawAttendance.objects.get_or_create(
                                device=device,
                                user_id=str(att.user_id),
                                timestamp=aware_timestamp,
                                defaults={
                                    'status': att.status,
                                    'punch_state': getattr(att, 'punch', 0),
                                    'verify_type': getattr(att, 'verify_type', 0),
                                }
                            )
                            if created:
                                stored += 1
                    
                    device_result['raw_fetched'] = stored
                    results['total_raw_fetched'] += stored
                    
                except Exception as fetch_error:
                    # If fetch times out or fails, use existing data if available
                    device_result['error'] = f"Fetch failed: {str(fetch_error)}"
                
                conn.disconnect()
            
        except Exception as e:
            device_result['error'] = str(e)
        
        results['devices'].append(device_result)
    
    # Process attendance for the specific date (only for the devices we synced)
    try:
        if device_id:
            # Process only for the selected device
            processed_count = process_all_attendance_for_date(sync_date, device_id=device_id)
        else:
            # Process for all devices
            processed_count = process_all_attendance_for_date(sync_date)
        results['total_processed'] = processed_count
    except Exception as e:
        results['processing_error'] = str(e)
    
    return JsonResponse(results)


def dashboard(request):
    """
    Main dashboard showing overview of attendance system.
    """
    # Get recent attendance records
    recent_attendances = ProcessedAttendance.objects.select_related('device').order_by('-date', '-updated_at')[:20]
    
    # Get devices
    devices = Device.objects.all()
    
    # Get today's statistics
    today = timezone.now().date()
    today_attendances = ProcessedAttendance.objects.filter(date=today)
    
    context = {
        'recent_attendances': recent_attendances,
        'devices': devices,
        'today_stats': {
            'total': today_attendances.count(),
            'outliers': today_attendances.filter(is_outlier=True).count(),
            'unsynced': today_attendances.filter(synced_to_crm=False).count(),
        },
        'today': today,
    }
    
    return render(request, 'core/dashboard.html', context)
