from django.core.management.base import BaseCommand
from django.db import transaction
from vehicle.models import Trailer

class Command(BaseCommand):
    help = 'Creates 9 demo trailers for the database'

    def handle(self, *args, **kwargs):
        demo_trailers = [
            {
                "trailer_id": "TRL-001",
                "vin": "1UYVS2533CA000001",
                "maker": "Utility",
                "model": "4000D-X Dry Van",
                "load_capacity": 25.00,
                "trailer_type": "trailer",
                "axle_count": 2,
                "status": "active"
            },
            {
                "trailer_id": "TRL-002",
                "vin": "1GRAA0624DA000002",
                "maker": "Great Dane",
                "model": "Champion CP",
                "load_capacity": 22.50,
                "trailer_type": "trailer",
                "axle_count": 2,
                "status": "idle"
            },
            {
                "trailer_id": "TRL-003",
                "vin": "1WABA1325EA000003",
                "maker": "Wabash",
                "model": "National DuraPlate",
                "load_capacity": 26.00,
                "trailer_type": "trailer",
                "axle_count": 2,
                "status": "idle"
            },
            {
                "trailer_id": "TRL-004",
                "vin": "1MACF0926FA000004",
                "maker": "MAC Trailer",
                "model": "Aluminum Flatbed",
                "load_capacity": 30.00,
                "trailer_type": "trailer",
                "axle_count": 2,
                "status": "under_maintenance"
            },
            {
                "trailer_id": "TRL-005",
                "vin": "1SILV0227GA000005",
                "maker": "Silver Eagle",
                "model": "Converter Gear",
                "load_capacity": 10.00,
                "trailer_type": "dolly",
                "axle_count": 1,
                "status": "active"
            },
            {
                "trailer_id": "TRL-006",
                "vin": "1FONT0428HA000006",
                "maker": "Fontaine",
                "model": "Velocity Drop Deck",
                "load_capacity": 28.00,
                "trailer_type": "trailer",
                "axle_count": 2,
                "status": "idle"
            },
            {
                "trailer_id": "TRL-007",
                "vin": "1HYUN0829JA000007",
                "maker": "Hyundai",
                "model": "Translead Thermotech",
                "load_capacity": 24.00,
                "trailer_type": "trailer",
                "axle_count": 2,
                "status": "active"
            },
            {
                "trailer_id": "TRL-008",
                "vin": "1DOON0730KA000008",
                "maker": "Doonan",
                "model": "Chaparrall II Lead",
                "load_capacity": 35.00,
                "trailer_type": "b_train",
                "axle_count": 3,
                "status": "idle"
            },
            {
                "trailer_id": "TRL-009",
                "vin": "1UYVR2531LA000009",
                "maker": "Utility",
                "model": "3000R Reefer",
                "load_capacity": 23.50,
                "trailer_type": "trailer",
                "axle_count": 2,
                "status": "under_maintenance"
            }
        ]

        # 2. Iterate and create
        try:
            with transaction.atomic():
                for trailer_data in demo_trailers:
                    t_id = trailer_data['trailer_id']
                    
                    # Check if trailer already exists to make the script idempotent
                    if Trailer.objects.filter(trailer_id=t_id).exists():
                        self.stdout.write(self.style.WARNING(f'Trailer {t_id} already exists. Skipping.'))
                        continue
                    
                    # Create the trailer
                    Trailer.objects.create(**trailer_data)
                    self.stdout.write(self.style.SUCCESS(f'Successfully created Trailer: {t_id}'))
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An error occurred: {str(e)}'))