from django.core.management.base import BaseCommand
from django.db import transaction
from vehicle.models import Tractor 
from vehicle.choices import ACTIVE, IDLE, UNDER_MAINTENANCE, INACTIVE

class Command(BaseCommand):
    help = 'Creates 9 demo tractors for the database'

    def handle(self, *args, **kwargs):
        demo_tractors = [
            {
                "tractor_id": "TRC-001",
                "vin": "1FUJHDCA1EL000001",
                "maker": "Freightliner",
                "model": "Cascadia",
                "axle_count": 0,
                "status": ACTIVE
            },
            {
                "tractor_id": "TRC-002",
                "vin": "1XP5DB9X3EN000002",
                "maker": "Peterbilt",
                "model": "579",
                "axle_count": 3,
                "status": IDLE
            },
            {
                "tractor_id": "TRC-003",
                "vin": "4V4NC9EJ2FN000003",
                "maker": "Volvo",
                "model": "VNL 860",
                "axle_count": 3,
                "status": ACTIVE
            },
            {
                "tractor_id": "TRC-004",
                "vin": "1XKAD49X5GN000004",
                "maker": "Kenworth",
                "model": "T680",
                "axle_count": 3,
                "status": UNDER_MAINTENANCE
            },
            {
                "tractor_id": "TRC-005",
                "vin": "1M2AK09C6HN000005",
                "maker": "Mack",
                "model": "Anthem",
                "axle_count": 1,
                "status": ACTIVE
            },
            {
                "tractor_id": "TRC-006",
                "vin": "1FUJEDCA7JL000006",
                "maker": "Freightliner",
                "model": "M2 106",
                "axle_count": 2,
                "status": IDLE
            },
            {
                "tractor_id": "TRC-007",
                "vin": "1XP4DB9X8KN000007",
                "maker": "Peterbilt",
                "model": "389",
                "axle_count": 3,
                "status": INACTIVE
            },
            {
                "tractor_id": "TRC-008",
                "vin": "4V4NC9EJ9LN000008",
                "maker": "Volvo",
                "model": "VNR 300",
                "axle_count": 2,
                "status": ACTIVE
            },
            {
                "tractor_id": "TRC-009",
                "vin": "1XKAD49X0MN000009",
                "maker": "Kenworth",
                "model": "W900",
                "axle_count": 3,
                "status": IDLE
            }
        ]

        # 2. Iterate and create
        try:
            with transaction.atomic():
                for tractor_data in demo_tractors:
                    t_id = tractor_data['tractor_id']
                    
                    # Check if tractor already exists to make the script idempotent
                    if Tractor.objects.filter(tractor_id=t_id).exists():
                        self.stdout.write(self.style.WARNING(f'Tractor {t_id} already exists. Skipping.'))
                        continue
                    
                    # Create the tractor
                    Tractor.objects.create(**tractor_data)
                    self.stdout.write(self.style.SUCCESS(f'Successfully created Tractor: {t_id}'))
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An error occurred: {str(e)}'))