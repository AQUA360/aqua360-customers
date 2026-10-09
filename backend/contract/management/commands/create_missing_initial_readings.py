from __future__ import annotations
import datetime
import uuid
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from contract.models import Contract
from billing.models import Reading


class Command(BaseCommand):
    help = (
        "Detects all contracts that do not have an initial reading, "
        "and creates one on the contract's creation date (using registration_date or created_at.date()), "
        "taking the same value as the last reading of the meter."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not create anything in the database; just show what would be done.",
        )
        parser.add_argument(
            "--include-inactive",
            action="store_true",
            help="Include contracts with is_active=False (default: only is_active=True).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        include_inactive = options["include_inactive"]

        from coredata.models import ConfigProject
        from contract.models import ContractStatus

        try:
            active_contract_token = ConfigProject.objects.get(token='contract_active_token').value
            active_status = ContractStatus.objects.get(token=active_contract_token)
            contracts_qs = Contract.objects.filter(status=active_status)
        except (ConfigProject.DoesNotExist, ContractStatus.DoesNotExist):
            self.stdout.write(self.style.ERROR("Active contract status configuration not found!"))
            return

        if not include_inactive:
            contracts_qs = contracts_qs.filter(is_active=True)

        self.stdout.write(f"Analyzing contracts (include_inactive={include_inactive})...")
        contracts_without_initial = []

        for contract in contracts_qs:
            # Check if any reading exists for this contract
            has_readings = Reading.objects.filter(
                contract=contract,
                is_active=True
            ).exists()
            
            if not has_readings:
                contracts_without_initial.append(contract)

        total_missing = len(contracts_without_initial)
        self.stdout.write(f"Found {total_missing} contracts without an initial reading.")

        created_count = 0

        with transaction.atomic():
            for contract in contracts_without_initial:
                # Find meter from default supply point or associated supply points
                meter = None
                supply_point = contract.supply_point_default
                if supply_point and supply_point.meter:
                    meter = supply_point.meter
                else:
                    sp_with_meter = contract.supply_points.filter(meter__isnull=False).first()
                    if sp_with_meter:
                        supply_point = sp_with_meter
                        meter = sp_with_meter.meter

                if not meter or not supply_point:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping Contract ID {contract.id} (Token: {contract.token}) because it has no supply point or meter."
                        )
                    )
                    continue

                # Get the last reading of the meter (before or at any time, to take the value)
                last_meter_reading = Reading.objects.filter(
                    meter=meter,
                    reading_value__isnull=False,
                    is_active=True
                ).order_by('-reading_date', '-created_at').first()

                reading_value = last_meter_reading.reading_value if last_meter_reading else 0.0

                target_date = contract.registration_date or contract.created_at.date()

                self.stdout.write(
                    f"Contract ID {contract.id} (Token: {contract.token}) -> "
                    f"Creating initial reading on {target_date} with value {reading_value} on Meter {meter.code} (SP {supply_point.id})"
                )

                if not dry_run:
                    Reading.objects.create(
                        token=str(uuid.uuid4()),
                        contract=contract,
                        supply_point=supply_point,
                        meter=meter,
                        reading_date=target_date,
                        reading_value=reading_value,
                        calculated_value=0.00,
                        is_initial=True,
                        is_estimated=False,
                        is_control=False,
                        is_active=True,
                        origin="Inicial"
                    )
                created_count += 1

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY-RUN] Process completed. Would have created {created_count} initial readings."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully created {created_count} initial readings."
                )
            )
