from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from vehicle.models import Tractor

from .views import TRACTOR_CACHE_KEY


@receiver(post_save, sender=Tractor)
@receiver(post_delete, sender=Tractor)
def invalidate_tractor_cache(sender, instance, **kwargs):
    cache.delete(TRACTOR_CACHE_KEY)
