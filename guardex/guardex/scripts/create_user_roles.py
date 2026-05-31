from user.models import UserRole
from user.choices import ROLE_CHOICES

def create_user_roles():
    for role in ROLE_CHOICES:
        UserRole.objects.get_or_create(name=role[0])
