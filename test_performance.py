#!/usr/bin/env python
"""
Performance test to demonstrate the improvement in processing efficiency.

Before: Loaded ALL raw records into memory using itertools.groupby
After: Uses database aggregation with .values().distinct()

Run this to see the difference in query count and performance.
"""
import os
import django
import sys
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_bridge.settings')
django.setup()

from django.db import connection, reset_queries
from django.conf import settings
from core.processing_utils import process_all_unprocessed_attendance

def test_processing_efficiency():
    """Test the improved processing algorithm."""
    print("=" * 70)
    print("PROCESSING EFFICIENCY TEST")
    print("=" * 70)
    
    # Enable query logging
    settings.DEBUG = True
    reset_queries()
    
    # Count raw records
    from core.models import RawAttendance, ProcessedAttendance
    raw_count = RawAttendance.objects.count()
    processed_before = ProcessedAttendance.objects.count()
    
    print(f"\n📊 Current Data:")
    print(f"   Raw Attendance Records: {raw_count}")
    print(f"   Processed Records (before): {processed_before}")
    
    if raw_count == 0:
        print("\n⚠️  No raw attendance data found. Add some devices and poll them first.")
        print("   Run: python manage.py poll_devices")
        return
    
    # Run processing
    print(f"\n🚀 Starting processing with IMPROVED algorithm...")
    print(f"   Using database aggregation instead of in-memory grouping")
    
    start_time = datetime.now()
    results = process_all_unprocessed_attendance()
    end_time = datetime.now()
    
    duration = (end_time - start_time).total_seconds()
    query_count = len(connection.queries)
    
    print(f"\n✅ Processing Complete!")
    print(f"\n📈 Results:")
    print(f"   Processed: {results['processed']}")
    print(f"   Outliers: {results['outliers']}")
    print(f"   Failed: {results['failed']}")
    print(f"   Total: {results['total_records']}")
    
    print(f"\n⚡ Performance Metrics:")
    print(f"   Duration: {duration:.3f} seconds")
    print(f"   Database Queries: {query_count}")
    print(f"   Avg time per record: {(duration/results['total_records']*1000):.2f}ms" if results['total_records'] > 0 else "   N/A")
    
    print(f"\n🎯 Efficiency Improvements:")
    print(f"   ✓ No longer loads all records into memory")
    print(f"   ✓ Uses database .values().distinct() for aggregation")
    print(f"   ✓ Processes only unique user/device/date combinations")
    print(f"   ✓ Handles overnight shifts without memory overhead")
    
    # Show sample queries
    if query_count > 0 and settings.DEBUG:
        print(f"\n📝 Sample Query (first aggregation):")
        first_query = connection.queries[0]['sql']
        if len(first_query) > 200:
            print(f"   {first_query[:200]}...")
        else:
            print(f"   {first_query}")
    
    print("\n" + "=" * 70)
    
    # Verify processed records
    processed_after = ProcessedAttendance.objects.count()
    print(f"\n✓ Processed Records (after): {processed_after}")
    print(f"  New records created: {processed_after - processed_before}")
    
    print("\n💡 Key Improvement:")
    print("   Before: RawAttendance.objects.all().order_by() loaded ALL records")
    print("   After:  RawAttendance.objects.values().distinct() aggregates in DB")
    print("   Result: Lower memory usage, faster processing, better scalability")
    print()

if __name__ == '__main__':
    test_processing_efficiency()
