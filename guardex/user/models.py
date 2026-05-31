from django.db import models
from guardex.models.TimeStamp import TimeStamp
from django.contrib.auth.models import  BaseUserManager, AbstractBaseUser, PermissionsMixin, UserManager
from phonenumber_field.modelfields import PhoneNumberField
from .choices import ROLE_CHOICES


class UserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('The Phone Number field must be set')
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(phone_number, password, **extra_fields)
    

class Organization(TimeStamp):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
    
   
class UserRole(TimeStamp):
    
    name = models.CharField(choices=ROLE_CHOICES, unique=True, default='driver')

    def __str__(self):
        return self.get_name_display()


class User(AbstractBaseUser, PermissionsMixin, TimeStamp):
    email = models.EmailField(unique=True, blank=True, null=True)
    first_name = models.CharField(max_length=50, null=True, blank=True)
    last_name = models.CharField(max_length=50, null=True, blank=True)
    phone_number = PhoneNumberField(unique=True)
    alternate_phone_number = PhoneNumberField( null=True, blank=True)
    user_role = models.ForeignKey(UserRole, on_delete=models.SET_NULL, blank=True, null=True, related_name='users')
    license_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    license_expiry_date = models.DateField(null=True, blank=True)
    medcard_number = models.CharField(max_length=50, null=True, blank=True)
    medcard_expiry_date = models.DateField(null=True, blank=True)
    endorsement = models.CharField(max_length=100, null=True, blank=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='users',null=True, blank=True)   
    objects = UserManager()
    
    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []
    
    def __str__(self):
        return str(self.phone_number)
