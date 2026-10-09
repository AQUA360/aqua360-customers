from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from django.core.management.base import BaseCommand
from django.db import transaction

from billing.models import Invoice


@dataclass(frozen=True)
class _BatchResult:
    invoices_seen: int
    invoices_updated: int


def _chunked(items: List[Invoice], chunk_size: int) -> Iterable[List[Invoice]]:
    for i in range(0, len(items), chunk_size):
        yield items[i : i + chunk_size]


class Command(BaseCommand):
    help = (
        "Backfills payment_type/payment_bank/payment_company_bank (and their *_final "
        "snapshot fields) on invoices that were generated before the contract's payment "
        "was linked, copying the data from the contract's current GeneralPayment. "
        "Only touches invoices whose payment_type FK is currently null, and never "
        "overwrites an invoice that already has one."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Writes nothing to DB; only shows how many invoices would be affected.",
        )
        parser.add_argument(
            "--billing-id",
            type=int,
            default=None,
            help="Restrict the backfill to invoices of a single Billing run (billing_invoice.billing_id).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of invoices to process (for testing).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Batch size for bulk_update.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        billing_id: Optional[int] = options["billing_id"]
        limit: Optional[int] = options["limit"]
        batch_size: int = options["batch_size"]

        if batch_size <= 0:
            raise ValueError("--batch-size must be > 0")
        if limit is not None and limit <= 0:
            raise ValueError("--limit must be > 0")

        invoices = self._collect_invoices(billing_id, limit)
        total = len(invoices)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY-RUN] Invoices with payment_type missing but contract has one: {total}."
                )
            )
            for invoice in invoices[:20]:
                payment = invoice.contract.payment
                self.stdout.write(
                    f"  - invoice={invoice.serie_final or invoice.token} (id={invoice.id}) "
                    f"contract={invoice.contract.token} -> "
                    f"payment_type={payment.type.token}"
                )
            if total > 20:
                self.stdout.write(f"  ... and {total - 20} more")
            return

        result = self._process_in_batches(invoices, batch_size=batch_size)
        self.stdout.write(
            self.style.SUCCESS(
                "OK. "
                f"Invoices seen={result.invoices_seen}, "
                f"invoices updated={result.invoices_updated}"
            )
        )

    def _collect_invoices(self, billing_id: Optional[int], limit: Optional[int]) -> List[Invoice]:
        qs = Invoice.objects.filter(
            payment_type__isnull=True,
            contract__payment__isnull=False,
            contract__payment__type__isnull=False,
        ).select_related(
            "contract__payment__type",
            "contract__payment__IBAN",
            "contract__payment__company_iban",
        ).only(
            "id",
            "token",
            "serie_final",
            "payment_type",
            "payment_bank",
            "payment_company_bank",
            "payment_type_final",
            "payment_type_token_final",
            "payment_bank_final",
            "payment_swift_final",
            "contract__id",
            "contract__token",
            "contract__payment__type__name",
            "contract__payment__type__token",
            "contract__payment__IBAN__iban",
            "contract__payment__IBAN__swift",
            "contract__payment__company_iban__iban",
            "contract__payment__company_iban__swift",
        ).order_by("id")

        if billing_id is not None:
            qs = qs.filter(billing_id=billing_id)
        if limit is not None:
            qs = qs[:limit]

        return list(qs)

    def _process_in_batches(self, invoices: List[Invoice], batch_size: int) -> _BatchResult:
        invoices_seen = 0
        invoices_updated = 0

        for batch in _chunked(invoices, batch_size):
            updated = self._process_batch(batch)
            invoices_seen += len(batch)
            invoices_updated += updated

        return _BatchResult(invoices_seen=invoices_seen, invoices_updated=invoices_updated)

    def _process_batch(self, batch: List[Invoice]) -> int:
        if not batch:
            return 0

        for invoice in batch:
            payment = invoice.contract.payment
            payment_type = payment.type
            payment_bank_instance = payment.IBAN
            payment_company_bank_instance = payment.company_iban

            invoice.payment_type = payment_type
            invoice.payment_bank = payment_bank_instance
            invoice.payment_company_bank = payment_company_bank_instance
            invoice.payment_type_final = payment_type.name
            invoice.payment_type_token_final = payment_type.token
            invoice.payment_bank_final = (
                payment_company_bank_instance.iban
                if payment_company_bank_instance
                else (payment_bank_instance.iban if payment_bank_instance else None)
            )
            invoice.payment_swift_final = (
                payment_company_bank_instance.swift
                if payment_company_bank_instance
                else (payment_bank_instance.swift if payment_bank_instance else None)
            )

        with transaction.atomic():
            Invoice.objects.bulk_update(
                batch,
                [
                    "payment_type",
                    "payment_bank",
                    "payment_company_bank",
                    "payment_type_final",
                    "payment_type_token_final",
                    "payment_bank_final",
                    "payment_swift_final",
                ],
                batch_size=len(batch),
            )

        return len(batch)
