from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, List, Optional, Tuple

from django.core.management.base import BaseCommand
from django.db import transaction

from contract.models import Contract, PiggyBank


@dataclass(frozen=True)
class _BatchResult:
    contracts_seen: int
    piggy_banks_created: int
    contracts_updated: int


def _chunked(items: List[Contract], chunk_size: int) -> Iterable[List[Contract]]:
    for i in range(0, len(items), chunk_size):
        yield items[i : i + chunk_size]


def _piggy_token_for_contract(contract: Contract) -> str:
    """
    Uses Contract.token if present, otherwise generates a deterministic token.
    """
    if contract.token:
        return str(contract.token)
    return f"backfill-contract-{contract.id}"


class Command(BaseCommand):
    help = "Creates PiggyBank for all contracts without piggy_bank and links the relation."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="No escribe nada en BD; solo muestra cuántos registros afectaría.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of contracts to process (for testing).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=2000,
            help="Tamaño de lote para bulk_create/bulk_update.",
        )
        parser.add_argument(
            "--include-inactive",
            action="store_true",
            help="Include contracts with is_active=False (default: only is_active=True).",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        limit: Optional[int] = options["limit"]
        batch_size: int = options["batch_size"]
        include_inactive: bool = options["include_inactive"]

        if batch_size <= 0:
            raise ValueError("--batch-size must be > 0")
        if limit is not None and limit <= 0:
            raise ValueError("--limit must be > 0")

        qs = Contract.objects.filter(piggy_bank__isnull=True, holder__isnull=False)
        if not include_inactive:
            qs = qs.filter(is_active=True)

        qs = qs.only(
            "id",
            "token",
            "holder_id",
            "piggy_bank_id",
            "is_active",
        )

        if limit is not None:
            qs = qs.order_by("id")[:limit]

        contracts = list(qs)
        total = len(contracts)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY-RUN] Contratos sin piggy_bank encontrados: {total}. "
                    f"Se crearían {total} PiggyBank y se actualizarían {total} contratos."
                )
            )
            return

        result = self._process_in_batches(contracts, batch_size=batch_size)
        self.stdout.write(
            self.style.SUCCESS(
                "OK. "
                f"Contracts seen={result.contracts_seen}, "
                f"PiggyBanks created={result.piggy_banks_created}, "
                f"Contracts updated={result.contracts_updated}"
            )
        )

    def _process_in_batches(self, contracts: List[Contract], batch_size: int) -> _BatchResult:
        contracts_seen = 0
        piggy_banks_created = 0
        contracts_updated = 0

        for batch in _chunked(contracts, batch_size):
            batch_result = self._process_batch(batch)
            contracts_seen += batch_result[0]
            piggy_banks_created += batch_result[1]
            contracts_updated += batch_result[2]

        return _BatchResult(
            contracts_seen=contracts_seen,
            piggy_banks_created=piggy_banks_created,
            contracts_updated=contracts_updated,
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


