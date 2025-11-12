"""
Management command to sync processed attendance to CRM.
"""
from django.core.management.base import BaseCommand
from core.crm_utils import (
    sync_unsynced_attendance,
    sync_by_date_range,
    sync_by_user,
    retry_failed_syncs
)
from datetime import datetime


class Command(BaseCommand):
    help = 'Sync processed attendance records to remote CRM'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            help='Maximum number of records to sync',
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date (YYYY-MM-DD) for date range sync',
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date (YYYY-MM-DD) for date range sync',
        )
        parser.add_argument(
            '--user-id',
            type=str,
            help='Sync only for specific user ID',
        )
        parser.add_argument(
            '--retry-failed',
            action='store_true',
            help='Retry previously failed syncs',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force resync even already synced records',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting CRM sync...'))
        
        try:
            if options['retry_failed']:
                self.stdout.write("Retrying failed syncs")
                results = retry_failed_syncs()
            
            elif options['user_id']:
                start_date = None
                end_date = None
                
                if options['start_date']:
                    start_date = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
                if options['end_date']:
                    end_date = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
                
                self.stdout.write(f"Syncing for user: {options['user_id']}")
                results = sync_by_user(
                    options['user_id'],
                    start_date=start_date,
                    end_date=end_date,
                    force_resync=options['force']
                )
            
            elif options['start_date']:
                start_date = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
                end_date = None
                
                if options['end_date']:
                    end_date = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
                
                self.stdout.write(f"Syncing date range: {start_date} to {end_date or 'today'}")
                results = sync_by_date_range(
                    start_date,
                    end_date=end_date,
                    force_resync=options['force']
                )
            
            else:
                self.stdout.write("Syncing all unsynced records")
                results = sync_unsynced_attendance(limit=options['limit'])
            
            self.stdout.write(self.style.SUCCESS(f"\nSync completed:"))
            self.stdout.write(f"  Total: {results['total']}")
            self.stdout.write(f"  Successful: {results['successful']}")
            self.stdout.write(f"  Failed: {results['failed']}")
            
            if results['errors']:
                self.stdout.write(self.style.WARNING(f"\nErrors:"))
                for error in results['errors'][:10]:  # Show first 10 errors
                    self.stdout.write(
                        self.style.ERROR(
                            f"  User {error['user_id']} on {error['date']}: {error['error']}"
                        )
                    )
                if len(results['errors']) > 10:
                    self.stdout.write(f"  ... and {len(results['errors']) - 10} more errors")
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            raise
