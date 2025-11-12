"""
Management command to test device connection.
"""
from django.core.management.base import BaseCommand
from core.device_utils import test_device_connection, get_device_info
from core.models import Device


class Command(BaseCommand):
    help = 'Test connection to ZKTeco devices'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ip',
            type=str,
            help='IP address to test (tests without saving to database)',
        )
        parser.add_argument(
            '--port',
            type=int,
            default=4370,
            help='Port number (default: 4370)',
        )
        parser.add_argument(
            '--device-id',
            type=int,
            help='Test specific device from database',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Test all devices in database',
        )

    def handle(self, *args, **options):
        if options['ip']:
            # Test connection to IP without database
            self.stdout.write(f"Testing connection to {options['ip']}:{options['port']}...")
            success = test_device_connection(options['ip'], options['port'])
            
            if success:
                self.stdout.write(self.style.SUCCESS(f"✓ Connection successful!"))
            else:
                self.stdout.write(self.style.ERROR(f"✗ Connection failed"))
        
        elif options['device_id']:
            # Test specific device from database
            try:
                device = Device.objects.get(id=options['device_id'])
                self.stdout.write(f"Testing device: {device.name} ({device.ip_address}:{device.port})")
                
                info = get_device_info(device)
                
                if info:
                    self.stdout.write(self.style.SUCCESS(f"✓ Connection successful!"))
                    self.stdout.write(f"\nDevice Information:")
                    self.stdout.write(f"  Name: {info['device_name']}")
                    self.stdout.write(f"  IP: {info['ip_address']}:{info['port']}")
                    self.stdout.write(f"  Firmware: {info['firmware_version']}")
                    self.stdout.write(f"  Serial: {info['serial_number']}")
                    self.stdout.write(f"  Platform: {info['platform']}")
                    self.stdout.write(f"  Users: {info['user_count']}")
                    self.stdout.write(f"  Attendance Records: {info['attendance_count']}")
                else:
                    self.stdout.write(self.style.ERROR(f"✗ Connection failed"))
            
            except Device.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Device with ID {options['device_id']} not found"))
        
        elif options['all']:
            # Test all devices in database
            devices = Device.objects.all()
            
            if not devices.exists():
                self.stdout.write(self.style.WARNING("No devices found in database"))
                return
            
            self.stdout.write(f"Testing {devices.count()} devices...\n")
            
            for device in devices:
                self.stdout.write(f"Testing {device.name} ({device.ip_address}:{device.port})...")
                
                success = test_device_connection(device.ip_address, device.port)
                
                if success:
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Connection successful"))
                else:
                    self.stdout.write(self.style.ERROR(f"  ✗ Connection failed"))
        
        else:
            self.stdout.write(self.style.ERROR("Please specify --ip, --device-id, or --all"))
