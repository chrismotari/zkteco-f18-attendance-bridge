"""
URL configuration for core app API and web views.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DeviceViewSet, 
    RawAttendanceViewSet, 
    ProcessedAttendanceViewSet,
    dashboard,
    attendance_report,
    attendance_print,
    sync_day,
    delete_attendance,
    reprocess_attendance,
    device_list,
    device_create,
    device_edit,
    device_delete,
    device_test,
    device_users,
    device_user_sync,
    device_user_delete,
    device_user_delete_from_db,
)

# Create a router and register our viewsets
router = DefaultRouter()
router.register(r'devices', DeviceViewSet, basename='device')
router.register(r'raw-attendance', RawAttendanceViewSet, basename='raw-attendance')
router.register(r'processed-attendance', ProcessedAttendanceViewSet, basename='processed-attendance')

# The API URLs are determined automatically by the router
urlpatterns = [
    # Web views
    path('', dashboard, name='dashboard'),
    path('report/', attendance_report, name='attendance_report'),
    path('report/print/', attendance_print, name='attendance_print'),
    path('sync-day/', sync_day, name='sync_day'),
    path('attendance/delete/', delete_attendance, name='delete_attendance'),
    path('attendance/reprocess/', reprocess_attendance, name='reprocess_attendance'),
    
    # Device management views
    path('devices/', device_list, name='device_list'),
    path('devices/create/', device_create, name='device_create'),
    path('devices/<int:device_id>/edit/', device_edit, name='device_edit'),
    path('devices/<int:device_id>/delete/', device_delete, name='device_delete'),
    path('devices/<int:device_id>/test/', device_test, name='device_test'),
    
    # Device user management views
    path('devices/<int:device_id>/users/', device_users, name='device_users'),
    path('devices/<int:device_id>/users/sync/', device_user_sync, name='device_user_sync'),
    path('devices/<int:device_id>/users/delete/', device_user_delete, name='device_user_delete'),
    path('devices/<int:device_id>/users/delete-from-db/', device_user_delete_from_db, name='device_user_delete_from_db'),
    
    # API endpoints
    path('api/', include(router.urls)),
]
