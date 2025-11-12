"""
Management command to process raw attendance data.
"""
from django.core.management.base import BaseCommand
from core.processing_utils import (
    process_all_unprocessed_attendance,
    process_attendance_for_date_range
)
from datetime import datetime


class Command(BaseCommand):
    help = 'Process raw attendance logs into clock-in/clock-out records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date (YYYY-MM-DD)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting attendance processing...'))
        
        try:
            if options['start_date']:
                start_date = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
                end_date = None
                
                if options['end_date']:
                    end_date = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
                
                self.stdout.write(f"Processing date range: {start_date} to {end_date or 'today'}")
                results = process_attendance_for_date_range(start_date, end_date)
            else:
                self.stdout.write("Processing all unprocessed attendance")
                results = process_all_unprocessed_attendance()
            
            self.stdout.write(self.style.SUCCESS(f"\nProcessing completed:"))
            self.stdout.write(f"  Total records: {results['total_records']}")
            self.stdout.write(f"  Processed: {results['processed']}")
            self.stdout.write(f"  Outliers: {results['outliers']}")
            self.stdout.write(f"  Failed: {results['failed']}")
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            raise
