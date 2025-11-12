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
    sync_day
    , delete_attendance
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
    
    # API endpoints
    path('api/', include(router.urls)),
]
