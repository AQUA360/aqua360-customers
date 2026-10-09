from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, List, Optional, Tuple

from django.core.management.base import BaseCommand
from django.db import transaction
from service.models import SupplyPoint

from billing.models import EstimatedBag
from contract.models import Contract


@dataclass(frozen=True)
class _BatchResult:
    pairs_seen: int
    estimated_bags_created: int


def _chunked(
    items: List[Tuple[Contract, SupplyPoint]], chunk_size: int
) -> Iterable[List[Tuple[Contract, SupplyPoint]]]:
    for i in range(0, len(items), chunk_size):
        yield items[i : i + chunk_size]


def _estimated_bag_token_for(contract: Contract, supply_point_id: int) -> str:
    """
    Deterministic token for EstimatedBag (contract + supply_point).
    """
    if contract.token:
        return f"{contract.token}-sp-{supply_point_id}"
    return f"backfill-contract-{contract.id}-sp-{supply_point_id}"


class Command(BaseCommand):
    help = "Creates EstimatedBag for all (contract, supply_point) pairs that are missing one."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Writes nothing to DB; only shows how many records would be affected.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of (contract, supply_point) pairs to process (for testing).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=2000,
            help="Batch size for bulk_create.",
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

        missing_pairs = self._collect_missing_pairs(include_inactive, limit)
        total = len(missing_pairs)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY-RUN] (contract, supply_point) pairs without EstimatedBag: {total}. "
                    f"Would create {total} EstimatedBag(s)."
                )
            )
            return

        result = self._process_in_batches(missing_pairs, batch_size=batch_size)
        self.stdout.write(
            self.style.SUCCESS(
                "OK. "
                f"Pairs seen={result.pairs_seen}, "
                f"EstimatedBags created={result.estimated_bags_created}"
            )
        )

    def _collect_missing_pairs(
        self, include_inactive: bool, limit: Optional[int]
    ) -> List[Tuple[Contract, SupplyPoint]]:
        qs = Contract.objects.filter(supply_points__isnull=False).prefetch_related("supply_points")
        if not include_inactive:
            qs = qs.filter(is_active=True)
        qs = qs.only("id", "token")

        existing = set(
            EstimatedBag.objects.filter(contract__isnull=False, supply_point__isnull=False).values_list(
                "contract_id", "supply_point_id"
            )
        )

        pairs: List[Tuple[Contract, SupplyPoint]] = []
        seen = set()
        for contract in qs:
            for supply_point in contract.supply_points.all():
                key = (contract.id, supply_point.id)
                if key in existing or key in seen:
                    continue
                seen.add(key)
                pairs.append((contract, supply_point))
                if limit is not None and len(pairs) >= limit:
                    return pairs
        return pairs

    def _process_in_batches(
        self, pairs: List[Tuple[Contract, SupplyPoint]], batch_size: int
    ) -> _BatchResult:
        pairs_seen = 0
        estimated_bags_created = 0

        for batch in _chunked(pairs, batch_size):
            created = self._process_batch(batch)
            pairs_seen += len(batch)
            estimated_bags_created += created

        return _BatchResult(
            pairs_seen=pairs_seen,
            estimated_bags_created=estimated_bags_created,
        )

    def _process_batch(self, batch: List[Tuple[Contract, SupplyPoint]]) -> int:
        if not batch:
            return 0

        bags = [
            EstimatedBag(
                token=_estimated_bag_token_for(contract, supply_point.id),
                supply_point=supply_point,
                contract=contract,
                total_consumption=Decimal("0.00"),
                is_active=True,
            )
            for contract, supply_point in batch
        ]

        with transaction.atomic():
            EstimatedBag.objects.bulk_create(bags, batch_size=len(bags))

        return len(bags)
