"""
Management command to poll all enabled devices for attendance.
"""
from django.core.management.base import BaseCommand
from core.device_utils import poll_all_devices
from datetime import datetime, timedelta


class Command(BaseCommand):
    help = 'Poll all enabled ZKTeco devices for attendance logs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--since-hours',
            type=int,
            help='Only fetch records from the last N hours',
        )
        parser.add_argument(
            '--since-days',
            type=int,
            help='Only fetch records from the last N days',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting device polling...'))
        
        since = None
        if options['since_hours']:
            since = datetime.now() - timedelta(hours=options['since_hours'])
            self.stdout.write(f"Fetching records from last {options['since_hours']} hours")
        elif options['since_days']:
            since = datetime.now() - timedelta(days=options['since_days'])
            self.stdout.write(f"Fetching records from last {options['since_days']} days")
        
        try:
            results = poll_all_devices(since=since)
            
            self.stdout.write(self.style.SUCCESS(f"\nPolling completed:"))
            self.stdout.write(f"  Total devices: {results['total_devices']}")
            self.stdout.write(f"  Successful: {results['successful']}")
            self.stdout.write(f"  Failed: {results['failed']}")
            
            self.stdout.write(f"\nDevice details:")
            for device_result in results['devices']:
                if device_result['status'] == 'success':
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  ✓ {device_result['device']}: "
                            f"{device_result['new_records']} new records "
                            f"({device_result['total_fetched']} total fetched)"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"  ✗ {device_result['device']}: {device_result['error']}"
                        )
                    )
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            raise
