from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from billing.models import Invoice, InvoiceStatus, PaymentStatus, Payment
from coredata.models import ConfigProject


class Command(BaseCommand):
    help = (
        "Corregeix l'estat de factures que estan en un estat no pagat "
        "(Vençuda, Confirmada, etc.) però tots els seus pagaments estan en estat Pagat. "
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
            help="ID(s) de Factura a processar, separats per comes (ex: 123,456). "
            "Sense aquest argument, es processen totes les factures afectades.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        ids_raw: str = (options.get("id") or "").strip()

        try:
            paid_invoice_status = InvoiceStatus.objects.get(
                token=ConfigProject.objects.get(token='invoice_status_paid_token').value
            )
            cancelled_invoice_status = InvoiceStatus.objects.get(
                token=ConfigProject.objects.get(token='invoice_status_cancelled_token').value
            )
            payoff_invoice_status = InvoiceStatus.objects.get(
                token=ConfigProject.objects.get(token='invoice_status_payoff_token').value
            )
            paid_payment_status = PaymentStatus.objects.get(
                token=ConfigProject.objects.get(token='payment_status_paid_token').value
            )
        except (ConfigProject.DoesNotExist, InvoiceStatus.DoesNotExist, PaymentStatus.DoesNotExist) as e:
            self.stderr.write(self.style.ERROR(f"Error de configuració: {e}"))
            return

        invoice_ids = []
        if ids_raw:
            for part in ids_raw.split(","):
                part = part.strip()
                if part.isdigit():
                    invoice_ids.append(int(part))
                else:
                    self.stderr.write(self.style.ERROR(f"ID no vàlid: {part}"))
                    return

        qs = Invoice.objects.exclude(
            status__in=[paid_invoice_status, cancelled_invoice_status, payoff_invoice_status]
        ).filter(payments__isnull=False).distinct()

        if invoice_ids:
            qs = qs.filter(id__in=invoice_ids)

        affected = []
        for invoice in qs.select_related('status', 'contract'):
            invoice_payments = Payment.objects.filter(invoice=invoice)
            if not invoice_payments.exists():
                continue
            all_paid = not invoice_payments.exclude(status=paid_payment_status).exists()
            if all_paid:
                affected.append(invoice)

        if not affected:
            self.stdout.write(self.style.SUCCESS("No hi ha factures amb estat inconsistent per corregir."))
            return

        self.stdout.write(f"Factures afectades: {len(affected)}")

        for invoice in affected:
            contract_id = invoice.contract_id or 'N/A'
            old_status = invoice.status
            self.stdout.write(
                f"  Factura ID {invoice.id} ({invoice.token or invoice.number or 'Sense token'}) "
                f"Contracte ID {contract_id}: '{old_status}' → 'Pagada'"
            )

        if dry_run:
            self.stdout.write(self.style.WARNING(f"[DRY-RUN] S'actualitzarien {len(affected)} factures."))
            return

        with transaction.atomic():
            for invoice in affected:
                invoice.status = paid_invoice_status
                invoice.save(update_fields=['status'])

        self.stdout.write(self.style.SUCCESS(f"OK. {len(affected)} factures actualitzades a estat 'Pagada'."))
