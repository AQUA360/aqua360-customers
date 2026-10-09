from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.management.base import BaseCommand

if TYPE_CHECKING:
    from django.apps.registry import Apps


class Command(BaseCommand):
    help = (
        "Find modified readings and relate them to the original readings"
    )

    def handle(self, *args, **options):

        relate_modified_readings()


def relate_modified_readings(apps: Apps | None = None):
    if apps is not None:
        Reading = apps.get_model("billing", "Reading")
    else:
        from billing.models import Reading

    readings = Reading.objects.filter(origin__contains="Mod").distinct()
    print("readings", readings.count())

    for reading in readings:
        og_reading = (
            Reading.objects.filter(
                contract=reading.contract,
                reading_date=reading.reading_date,
                meter=reading.meter,
                is_control=True,
            )
            .exclude(id=reading.id)
            .exclude(origin__contains="MOD")
            .first()
        )
        if not og_reading:
            print(
                f"no og_reading found for reading {reading.id} for contract {reading.contract.token}"
            )
            continue

        og_reading.modified_readings.add(reading)
        og_reading.save()

    for reading in readings:
        if reading.original_readings.count() == 0:
            print(
                f"reading {reading.id} for contract {reading.contract.token} has no original readings"
            )
            continue
