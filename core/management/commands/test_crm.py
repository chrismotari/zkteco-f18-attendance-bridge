"""
Management command to test CRM connection.
"""
from django.core.management.base import BaseCommand
from core.crm_utils import test_crm_connection, get_sync_statistics


class Command(BaseCommand):
    help = 'Test connection to remote CRM API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show sync statistics',
        )

    def handle(self, *args, **options):
        if options['stats']:
            self.stdout.write(self.style.SUCCESS('Fetching sync statistics...'))
            stats = get_sync_statistics()
            
            self.stdout.write(f"\nSync Statistics:")
            self.stdout.write(f"  Total records: {stats['total']}")
            self.stdout.write(f"  Synced: {stats['synced']} ({stats['sync_percentage']:.1f}%)")
            self.stdout.write(f"  Unsynced: {stats['unsynced']}")
            self.stdout.write(f"  Failed (3+ attempts): {stats['failed']}")
        
        else:
            self.stdout.write('Testing CRM API connection...')
            
            success, message = test_crm_connection()
            
            if success:
                self.stdout.write(self.style.SUCCESS(f"✓ {message}"))
            else:
                self.stdout.write(self.style.ERROR(f"✗ {message}"))
