import random

from celery import shared_task

from vehicle import choices as VehicleChoices
from vehicle.models import Tractor


@shared_task
def log_tractor_status(tractor_id):
    tractor = Tractor.objects.get(tractor_id=tractor_id)
    print(f"[log_tractor_status] {tractor.maker} {tractor.model} ({tractor.tractor_id}) - status: {tractor.status}")
    return {
        "tractor_id": tractor.tractor_id,
        "status": tractor.status,
    }


@shared_task
def log_fleet_status_summary():
    summary = {
        status: Tractor.objects.filter(status=status).count()
        for status, _label in VehicleChoices.STATUS_CHOICES
    }
    print(f"[log_fleet_status_summary] {summary}")
    return summary


@shared_task(autoretry_for=(ConnectionError,), retry_backoff=True, max_retries=3)
def sync_tractor_with_external_system(tractor_id):
    tractor = Tractor.objects.get(tractor_id=tractor_id)

    if random.random() < 0.7:
        raise ConnectionError("simulated external system timeout")

    print(f"[sync_tractor_with_external_system] synced {tractor.tractor_id} successfully")
    return {"tractor_id": tractor.tractor_id, "synced": True}
