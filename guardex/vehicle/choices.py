ACTIVE = 'active'
INACTIVE = 'inactive'
UNDER_MAINTENANCE = 'under_maintenance'
IDLE = 'idle'

STATUS_CHOICES = (
    (ACTIVE, 'Active'),
    (INACTIVE, 'Inactive'),
    (UNDER_MAINTENANCE, 'Under maintenance'),
    (IDLE, 'Idle'),
)

TIRE_TYPE_CHOICES = (
    ('single', 'Single'),
    ('double', 'Double'),
)

DOLLY = 'dolly'
TRAILER = 'trailer' 
B_TRAIN = 'b_train'

TRAILER_TYPE_CHOICES = [
    (DOLLY, 'Dolly'),
    (TRAILER, 'Trailer'),
    (B_TRAIN, 'B-Train'),
]