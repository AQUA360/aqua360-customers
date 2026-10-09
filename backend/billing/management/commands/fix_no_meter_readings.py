from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.management.base import BaseCommand

if TYPE_CHECKING:
    from django.apps.registry import Apps


class Command(BaseCommand):
    help = "Fix estimated readings for meters in the configured no-meter status."

    def handle(self, *args, **options):

        fix_no_meter_readings_estimation()


def fix_no_meter_readings_estimation(apps: Apps | None = None):
    if apps is not None:
        ConfigProject = apps.get_model("coredata", "ConfigProject")
        MeterStatus = apps.get_model("service", "MeterStatus")
        Reading = apps.get_model("billing", "Reading")
        Contract = apps.get_model("contract", "Contract")
        EstimatedBag = apps.get_model("billing", "EstimatedBag")
        EstimatedBagMovement = apps.get_model("billing", "EstimatedBagMovement")
    else:
        from billing.models import EstimatedBag, EstimatedBagMovement, Reading
        from contract.models import Contract
        from coredata.models import ConfigProject
        from service.models import Meter, MeterStatus

    try:
        token_meter_status_no_meter = ConfigProject.objects.get(
            token="token_meter_status_no_meter"
        ).value
        status_no_meter = MeterStatus.objects.get(token=token_meter_status_no_meter)
    except Exception:
        print("no token_meter_status_no_meter found")
        return
    readings = Reading.objects.filter(
        meter__status__token=token_meter_status_no_meter,
        is_estimated=True,
    ).distinct()
    print("readings", readings.count())

    contracts = Contract.objects.filter(id__in=readings.values_list("contract_id", flat=True))

    for contract in contracts:
        estimated_bags = EstimatedBag.objects.filter(contract=contract)
        estimated_bags_movements = EstimatedBagMovement.objects.filter(
            estimated_bag__in=estimated_bags
        )
        estimated_bags_movements.delete()
        estimated_bags.update(total_consumption=0)

    readings.update(is_estimated=False, origin=status_no_meter.name)