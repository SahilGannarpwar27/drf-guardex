from django.db import models
from . import choices as VehicleChoices
from guardex.models.TimeStamp import TimeStamp

class Tractor(TimeStamp):

    PREFIX = "TRC"
    tractor_id = models.CharField(max_length=20, unique=True)
    vin = models.CharField(max_length=17, unique=True, help_text="Vehicle Identification Number")
    maker = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    axle_count = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=VehicleChoices.STATUS_CHOICES, default=VehicleChoices.IDLE)

    class Meta:
        ordering = ['tractor_id']

    def __str__(self):
        return f"{self.maker} {self.model} - {self.tractor_id}"
    
class Trailer(TimeStamp):

    PREFIX = "TRL"
    trailer_id = models.CharField(max_length=20, unique=True)
    vin = models.CharField(max_length=17, unique=True, help_text="Vehicle Identification Number")
    maker = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    load_capacity = models.DecimalField(max_digits=10, decimal_places=2, help_text="Load capacity in tons or kg")
    trailer_type = models.CharField(max_length=50, choices=VehicleChoices.TRAILER_TYPE_CHOICES, help_text="Type of trailer (Dolly, Trailer, B-Train)", default=VehicleChoices.TRAILER)
    axle_count = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=VehicleChoices.STATUS_CHOICES, default=VehicleChoices.IDLE)
    
    class Meta:
        ordering = ['trailer_id']

    def __str__(self):
        return f"{self.maker} {self.model} - {self.trailer_id}"
    
class Trip(TimeStamp):

    PREFIX = "TRK"
    trip_id = models.CharField(max_length=20, unique=True)
    pickup_date = models.DateField(blank=True, null=True)
    delivery_date = models.DateField(blank=True, null=True)
    is_notify_driver = models.BooleanField(default=False)
    tractor = models.ForeignKey(Tractor, on_delete=models.PROTECT, related_name='trips')
    driver = models.ForeignKey('user.User', on_delete=models.PROTECT, related_name='trips', null=True, blank=True)
    trailer = models.ManyToManyField(Trailer, through='TripTrailerRel', related_name='trips')

    class Meta:
        ordering = ['trip_id']

    def __str__(self):
        return f"Trip {self.trip_id}"
    

class TripTrailerRel(TimeStamp):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='trip_trailer_relations')
    trailer = models.ForeignKey(Trailer, on_delete=models.CASCADE, related_name='trip_trailer_relations')

    class Meta:
        unique_together = ('trip', 'trailer')

    def __str__(self):
        return f"Trip {self.trip.trip_id} - Trailer {self.trailer.trailer_id}"