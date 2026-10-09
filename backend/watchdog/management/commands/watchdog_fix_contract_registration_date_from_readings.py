from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Min
from django.utils import timezone

from contract.models import Contract
from watchdog.contract_dates import (
    active_contract_status,
    contract_effective_date,
    contract_effective_date_source,
    readings_before_contract_effective_date,
)


class Command(BaseCommand):
    help = (
        "Per contractes actius amb lectures anteriors a la data efectiva del contracte "
        "(registration_date, o created_at si registration_date és buida), assigna "
        "registration_date i created_at a la data de la lectura més antiga en conflicte. "
        "Només aplica canvis si la diferència en dies és <= --max. "
        "Recomanat quan el watchdog detecta 'Contractes Actius amb Lectures Anteriors a Creació'."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--max",
            type=int,
            required=True,
            help=(
                "Dies màxims de diferència (data contracte - data lectura) per aplicar el fix "
                "(p.ex. 10 només arregla contractes amb lectures com a molt 10 dies abans)"
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra què es faria sense desar canvis",
        )
        parser.add_argument(
            "--contract-id",
            type=str,
            default="",
            help="ID(s) de contracte a processar, separats per comes (opcional)",
        )

    def handle(self, *args, **options):
        max_days = options["max"]
        dry_run = options["dry_run"]
        contract_ids_raw = (options.get("contract_id") or "").strip()

        if max_days < 0:
            self.stdout.write(self.style.ERROR("--max ha de ser >= 0."))
            return

        try:
            active_status = active_contract_status()
        except Exception as exc:
            self.stdout.write(
                self.style.ERROR(
                    f"No s'ha pogut obtenir l'estat actiu de contracte: {exc}"
                )
            )
            return

        invalid_readings = readings_before_contract_effective_date(active_status)

        if contract_ids_raw:
            id_list = []
            for raw in contract_ids_raw.split(","):
                raw = raw.strip()
                if not raw:
                    continue
                if not raw.isdigit():
                    self.stdout.write(
                        self.style.ERROR(f"ID de contracte no vàlid: {raw!r}")
                    )
                    return
                id_list.append(int(raw))
            invalid_readings = invalid_readings.filter(contract_id__in=id_list)

        by_contract = (
            invalid_readings.values("contract_id")
            .annotate(earliest_reading_date=Min("reading_date"))
        )

        if not by_contract:
            self.stdout.write(
                self.style.SUCCESS(
                    "No hi ha contractes actius amb lectures anteriors a la data del contracte."
                )
            )
            return

        updated = 0
        skipped = 0

        for row in by_contract.order_by("contract_id"):
            contract = Contract.objects.get(pk=row["contract_id"])
            effective = contract_effective_date(contract)
            earliest = row["earliest_reading_date"]
            days_diff = (effective - earliest).days
            date_source = contract_effective_date_source(contract)

            if days_diff > max_days:
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Contract ID {contract.id} ({contract.token}): "
                        f"omès (diferència {days_diff} dies > --max {max_days}); "
                        f"lectura més antiga {earliest}, data contracte {effective} ({date_source})"
                    )
                )
                continue

            old_registration = contract.registration_date
            old_created_at = contract.created_at
            reading_time = (
                contract.created_at.time() if contract.created_at else datetime.min.time()
            )
            new_created_at = timezone.make_aware(datetime.combine(earliest, reading_time))
            if dry_run:
                self.stdout.write(
                    f"[dry-run] Contract ID {contract.id} ({contract.token}): "
                    f"registration_date {old_registration!r} -> {earliest}, "
                    f"created_at {old_created_at!r} -> {new_created_at} "
                    f"(diferència {days_diff} dies, abans {effective} via {date_source})"
                )
            else:
                with transaction.atomic():
                    contract.registration_date = earliest
                    contract.created_at = new_created_at
                    contract.save(update_fields=["registration_date", "created_at"])
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Contract ID {contract.id} ({contract.token}): "
                        f"registration_date {old_registration!r} -> {earliest}, "
                        f"created_at {old_created_at!r} -> {new_created_at} "
                        f"(diferència {days_diff} dies)"
                    )
                )
            updated += 1

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}{updated} contracte(s) "
                f"{'preparat(s)' if dry_run else 'actualitzat(s)'}, "
                f"{skipped} omès(s) per superar --max {max_days}."
            )
        )
