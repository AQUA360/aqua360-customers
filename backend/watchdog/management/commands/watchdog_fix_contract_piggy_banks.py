from __future__ import annotations

from decimal import Decimal
from typing import Iterable, List, Optional, Tuple

from django.core.management.base import BaseCommand
from django.db import transaction

from contract.models import Contract, PiggyBank


def _chunked(items: List[Contract], chunk_size: int) -> Iterable[List[Contract]]:
    for i in range(0, len(items), chunk_size):
        yield items[i : i + chunk_size]


def _piggy_token_for_contract(contract: Contract) -> str:
    if contract.token:
        return str(contract.token)
    return f"backfill-contract-{contract.id}"


def _parse_ids(raw: str) -> Tuple[List[int], List[str]]:
    ids = []
    invalid = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        if part.isdigit():
            ids.append(int(part))
        else:
            invalid.append(part)
    return ids, invalid


class Command(BaseCommand):
    help = (
        "Crea PiggyBank per als Contract sense piggy_bank (mateix criteri que el watchdog sniff "
        "'Contracts without Piggybanks') i enllaça la relació. "
        "Recomanat després de: python manage.py watchdog sniff"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra què es faria sense desar canvis",
        )
        parser.add_argument(
            "--id",
            type=str,
            default="",
            help="ID(s) de Contract a processar, separats per comes (ex: 4306,4307). "
            "Sense aquest argument, es processen tots els contractes sense PiggyBank.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Nombre màxim de contractes a processar (per proves).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=2000,
            help="Mida de lot per bulk_create/bulk_update.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        ids_raw: str = (options.get("id") or "").strip()
        limit: Optional[int] = options["limit"]
        batch_size: int = options["batch_size"]

        if batch_size <= 0:
            raise ValueError("--batch-size must be > 0")
        if limit is not None and limit <= 0:
            raise ValueError("--limit must be > 0")

        contract_ids, invalid_ids = _parse_ids(ids_raw)
        if invalid_ids:
            self.stderr.write(
                self.style.ERROR(
                    f"IDs no vàlids (cal números enters): {', '.join(invalid_ids)}"
                )
            )
            return

        qs = Contract.objects.filter(piggy_bank__isnull=True)
        if contract_ids:
            qs = qs.filter(id__in=contract_ids)
            found_ids = set(qs.values_list("id", flat=True))
            missing_ids = sorted(set(contract_ids) - found_ids)
            for contract_id in missing_ids:
                self.stdout.write(
                    self.style.WARNING(
                        f"Contract id={contract_id}: no trobat o ja té PiggyBank; s'omet"
                    )
                )

        qs = qs.only("id", "token", "holder_id", "piggy_bank_id").order_by("id")
        if limit is not None:
            qs = qs[:limit]

        contracts = list(qs)
        total = len(contracts)

        if total == 0:
            self.stdout.write(
                self.style.SUCCESS("No hi ha contractes sense PiggyBank per processar.")
            )
            return

        without_holder = [c for c in contracts if c.holder_id is None]
        if without_holder:
            self.stdout.write(
                self.style.WARNING(
                    f"{len(without_holder)} contracte(s) sense holder; "
                    "es crearà PiggyBank amb person=NULL."
                )
            )

        if dry_run:
            for contract in contracts:
                self.stdout.write(
                    f"[dry-run] Contract id={contract.id} ({contract.token}): "
                    f"crear PiggyBank token={_piggy_token_for_contract(contract)!r}, "
                    f"person_id={contract.holder_id}"
                )
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY-RUN] Es crearien {total} PiggyBank i s'actualitzarien "
                    f"{total} contractes."
                )
            )
            return

        contracts_seen = 0
        piggy_banks_created = 0
        contracts_updated = 0

        for batch in _chunked(contracts, batch_size):
            seen, created, updated = self._process_batch(batch)
            contracts_seen += seen
            piggy_banks_created += created
            contracts_updated += updated
            for contract in batch:
                self.stdout.write(
                    f"Contract id={contract.id} ({contract.token}): "
                    f"PiggyBank id={contract.piggy_bank_id} creat i enllaçat"
                )

        self.stdout.write(
            self.style.SUCCESS(
                "OK. "
                f"Contracts seen={contracts_seen}, "
                f"PiggyBanks created={piggy_banks_created}, "
                f"Contracts updated={contracts_updated}"
            )
        )

    def _process_batch(self, batch: List[Contract]) -> Tuple[int, int, int]:
        batch = [c for c in batch if c.piggy_bank_id is None]
        if not batch:
            return (0, 0, 0)

        piggies = [
            PiggyBank(
                token=_piggy_token_for_contract(c),
                person_id=c.holder_id,
                amount=Decimal("0.00"),
                is_active=True,
            )
            for c in batch
        ]

        with transaction.atomic():
            created = PiggyBank.objects.bulk_create(piggies, batch_size=len(piggies))
            for contract, piggy in zip(batch, created):
                contract.piggy_bank = piggy

            Contract.objects.bulk_update(batch, ["piggy_bank"], batch_size=len(batch))

        return (len(batch), len(created), len(batch))
