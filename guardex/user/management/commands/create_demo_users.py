from django.core.management.base import BaseCommand
from django.db import transaction
from user.models import User, UserRole
from user.choices import ADMIN, FIELD_ASSISTANT, DRIVER

class Command(BaseCommand):
    help = 'Creates demo users for the database'

    def handle(self, *args, **kwargs):
        # 1. Define the demo data array
        demo_users = [
            # 1 Admin User (with email and names)
            {
                "phone_number": "+10000000001",
                "role_name": ADMIN,
                "first_name": "Alice",
                "last_name": "Admin",
                "email": "alice.admin@demo.com"
            },
            # 2 Field Assistants
            {
                "phone_number": "+10000000002",
                "role_name": FIELD_ASSISTANT,
                "first_name": "Bob",
                "last_name": "Assistant",
                "email": "bob.field@demo.com"
            },
            {
                "phone_number": "+10000000003",
                "role_name": FIELD_ASSISTANT,
            },
            # 3 Drivers
            {
                "phone_number": "+10000000004",
                "role_name": DRIVER,
                "first_name": "Charlie",
                "last_name": "Driver",
            },
            {
                "phone_number": "+10000000005",
                "role_name": DRIVER,
            },
            {
                "phone_number": "+10000000006",
                "role_name": DRIVER,
            }
        ]

        default_password = "Admin@123"

        # 2. Iterate through the array and create users safely
        try:
            with transaction.atomic():
                for user_data in demo_users:
                    phone = user_data.pop('phone_number')
                    role_name = user_data.pop('role_name')

                    # Skip if user already exists so you can run the script multiple times
                    if User.objects.filter(phone_number=phone).exists():
                        self.stdout.write(self.style.WARNING(f'User with phone {phone} already exists. Skipping.'))
                        continue

                    # Ensure the UserRole exists in the database
                    role, created = UserRole.objects.get_or_create(name=role_name)

                    # Create the user using your custom UserManager
                    User.objects.create_user(
                        phone_number=phone,
                        password=default_password,
                        user_role=role,
                        **user_data  # Unpacks the rest of the optional fields (first_name, email, etc.)
                    )
                    
                    self.stdout.write(self.style.SUCCESS(f'Successfully created {role_name} user: {phone}'))
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An error occurred: {str(e)}'))