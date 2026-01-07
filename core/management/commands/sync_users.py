"""
Management command to sync users from ZKTeco devices.
"""
import logging
from django.core.management.base import BaseCommand
from core.models import Device, DeviceUser
from core.device_utils import connect_device

logger = logging.getLogger('core')


class Command(BaseCommand):
    help = 'Sync users from ZKTeco devices'

    def add_arguments(self, parser):
        parser.add_argument(
            '--device',
            type=str,
            help='Device name to sync from (if not specified, syncs from all devices)',
        )

    def handle(self, *args, **options):
        device_name = options.get('device')
        
        if device_name:
            try:
                devices = [Device.objects.get(name=device_name)]
                self.stdout.write(f"Syncing users from device: {device_name}")
            except Device.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Device '{device_name}' not found"))
                return
        else:
            devices = Device.objects.filter(enabled=True)
            self.stdout.write(f"Syncing users from {devices.count()} enabled device(s)")
        
        total_synced = 0
        total_created = 0
        total_updated = 0
        
        for device in devices:
            self.stdout.write(f"\nConnecting to {device.name} ({device.ip_address})...")
            
            conn = connect_device(device)
            if not conn:
                self.stdout.write(self.style.ERROR(f"Failed to connect to {device.name}"))
                continue
            
            try:
                users = conn.get_users()
                self.stdout.write(f"Found {len(users)} users on device")
                
                for user in users:
                    user_obj, created = DeviceUser.objects.update_or_create(
                        user_id=str(user.user_id),
                        defaults={
                            'name': user.name or f"User {user.user_id}",
                            'privilege': user.privilege,
                            'password': user.password or '',
                            'group_id': str(user.group_id) if hasattr(user, 'group_id') else '',
                            'card_no': str(user.card_no) if hasattr(user, 'card_no') else '',
                            'device': device,
                        }
                    )
                    
                    if created:
                        total_created += 1
                        self.stdout.write(self.style.SUCCESS(f"  Created: {user_obj}"))
                    else:
                        total_updated += 1
                        self.stdout.write(f"  Updated: {user_obj}")
                    
                    total_synced += 1
                
                conn.disconnect()
                self.stdout.write(self.style.SUCCESS(f"Successfully synced users from {device.name}"))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error syncing users from {device.name}: {str(e)}"))
                logger.error(f"Error syncing users from {device.name}: {str(e)}")
                try:
                    conn.disconnect()
                except:
                    pass
        
        self.stdout.write(self.style.SUCCESS(
            f"\nSync complete: {total_synced} users synced "
            f"({total_created} created, {total_updated} updated)"
        ))
