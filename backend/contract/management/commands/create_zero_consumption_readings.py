from __future__ import annotations
import datetime
from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from contract.models import Contract
from billing.models import Reading
from service.models import Route
from coredata.utils.name_utils import generate_token


class Command(BaseCommand):
    help = (
        "For all active contracts in the given routes (default: 0, 999, 555), checks whether they have "
        "a reading in the last N months (default: 6). If they don't, creates a reading with 0 consumption "
        "(same value as the last reading of the contract)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--routes",
            type=str,
            default="0,999,555",
            help="Comma-separated route tokens (default: 0,999,555).",
        )
        parser.add_argument(
            "--months",
            type=int,
            default=6,
            help="Look-back window in months (default: 6).",
        )
        parser.add_argument(
            "--date",
            type=str,
            default="30-06-2026",
            help="Date of the new readings, DD-MM-YYYY or YYYY-MM-DD (default: 30-06-2026). The look-back window is computed from it.",
        )
        parser.add_argument(
            "--include-inactive",
            action="store_true",
            help="Include contracts with is_active=False or a non-active status (default: only active contracts).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not create anything in the database; just show what would be done.",
        )

    def parse_date(self, value):
        for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        raise CommandError(f"Invalid --date '{value}', expected DD-MM-YYYY or YYYY-MM-DD.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        months = options["months"]
        include_inactive = options["include_inactive"]
        route_tokens = [t.strip() for t in options["routes"].split(",") if t.strip()]

        reading_date = self.parse_date(options["date"])
        cutoff_date = reading_date - relativedelta(months=months)

        routes = Route.objects.filter(token__in=route_tokens)
        found_tokens = set(routes.values_list("token", flat=True))
        for missing in sorted(set(route_tokens) - found_tokens):
            self.stdout.write(self.style.WARNING(f"Route with token '{missing}' not found."))
        if not found_tokens:
            self.stdout.write(self.style.ERROR("No routes found, nothing to do."))
            return

        contracts_qs = Contract.objects.filter(
            supply_point_default__property__route_position__route__in=routes
        ).select_related(
            "supply_point_default__meter",
            "supply_point_default__property__route_position__route",
        )

        if not include_inactive:
            from coredata.models import ConfigProject
            from contract.models import ContractStatus

            try:
                active_contract_token = ConfigProject.objects.get(token="contract_active_token").value
                active_status = ContractStatus.objects.get(token=active_contract_token)
            except (ConfigProject.DoesNotExist, ContractStatus.DoesNotExist):
                self.stdout.write(self.style.ERROR("Active contract status configuration not found!"))
                return
            contracts_qs = contracts_qs.filter(status=active_status, is_active=True)

        contracts_qs = contracts_qs.distinct().order_by("id")

        self.stdout.write(
            f"Analyzing {contracts_qs.count()} contracts in routes {sorted(found_tokens)} "
            f"(no reading since {cutoff_date}, new reading date {reading_date}, include_inactive={include_inactive})..."
        )

        with_recent = 0
        created_count = 0
        skipped = []

        for contract in contracts_qs.iterator():
            has_recent_reading = Reading.objects.filter(
                contract=contract,
                is_active=True,
                reading_date__gte=cutoff_date,
            ).exists()
            if has_recent_reading:
                with_recent += 1
                continue

            supply_point = contract.supply_point_default
            route_token = supply_point.property.route_position.route.token

            # Last reading of the contract on its default supply point: its value is kept so consumption is 0
            last_reading = Reading.objects.filter(
                contract=contract,
                supply_point=supply_point,
                is_active=True,
                reading_value__isnull=False,
            ).order_by("-reading_date", "-id").first()

            if not last_reading:
                skipped.append(f"Contract {contract.id} ({contract.token}): no previous reading to take the value from.")
                continue

            if last_reading.reading_date and last_reading.reading_date >= reading_date:
                skipped.append(
                    f"Contract {contract.id} ({contract.token}): last reading date {last_reading.reading_date} "
                    f"is not before {reading_date}."
                )
                continue

            meter = supply_point.meter or last_reading.meter
            consumption_days = (
                (reading_date - last_reading.reading_date).days if last_reading.reading_date else None
            )

            self.stdout.write(
                f"{'[DRY-RUN] ' if dry_run else ''}Contract {contract.id} ({contract.token}) route {route_token} -> "
                f"reading on {reading_date} value {last_reading.reading_value} (0 consumption, "
                f"previous {last_reading.reading_date}, {consumption_days} days) "
                f"meter {meter.code if meter else '-'} SP {supply_point.id}"
            )

            if not dry_run:
                with transaction.atomic():
                    Reading.objects.create(
                        token=generate_token(Reading, "-id", "ZERO"),
                        contract=contract,
                        supply_point=supply_point,
                        meter=meter,
                        reading_date=reading_date,
                        reading_value=last_reading.reading_value,
                        calculated_value=0,
                        consumption_days=consumption_days,
                        previous_reading=last_reading,
                        is_initial=False,
                        is_estimated=False,
                        is_control=False,
                        is_active=True,
                        origin="LECTURA_ZERO_AUTO",
                    )
            created_count += 1

        if skipped:
            self.stdout.write(self.style.WARNING(f"\nSkipped ({len(skipped)}):"))
            for msg in skipped:
                self.stdout.write(f"  - {msg}")

        self.stdout.write("")
        self.stdout.write(f"Contracts with a reading in the last {months} months: {with_recent}")
        self.stdout.write(f"Contracts skipped: {len(skipped)}")
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"[DRY-RUN] Would have created {created_count} zero-consumption readings.")
            )
        else:
            self.stdout.write(self.style.SUCCESS(f"Created {created_count} zero-consumption readings."))
