from django.core.management.base import BaseCommand, CommandError

from billing.models import Invoice
from billing.utils.payment_service import disconnect_payment_signals, reconnect_payment_signals
from billing.management.commands.recalculate_billing_invoices import (
    _build_config_cache,
    recalculate_invoice_preserving_identity,
)


class Command(BaseCommand):
    help = (
        "Recalcula una factura conservant el mateix id, serie_final i data d'emissió. "
        "Recalcula línies, consums, dies i imports, actualitza les dades estàtiques de "
        "client, pagador i adreça, i actualitza el pagament si canvia el total."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--invoice-id",
            type=int,
            required=True,
            help="ID de la factura.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra què es faria sense aplicar canvis.",
        )
        parser.add_argument(
            "--regenerate-pdf",
            action="store_true",
            help="Regenera el PDF després del recàlcul.",
        )

    def handle(self, *args, **options):
        invoice_id = options["invoice_id"]
        dry_run = options["dry_run"]
        regenerate_pdf = options["regenerate_pdf"]

        invoice = (
            Invoice.objects.filter(id=invoice_id)
            .select_related("status", "contract")
            .prefetch_related("readings")
            .first()
        )
        if not invoice:
            raise CommandError(f"No s'ha trobat cap factura amb id={invoice_id}.")

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("--- Recalcular factura (preservant serie_final) ---"))
        self.stdout.write(f"Factura id: {invoice_id}")
        if dry_run:
            self.stdout.write(self.style.WARNING("MODE DRY-RUN"))
        self.stdout.write("")

        can_process = invoice.readings.exists() and invoice.contract_id
        status_token = invoice.status.token if invoice.status else "-"
        if dry_run:
            label = "RECALCULAR" if can_process else "OMESA"
            self.stdout.write(
                f"  [{label}] id={invoice.id} serie={invoice.serie_final} "
                f"issue_date={invoice.issue_date} total={invoice.total_final} status={status_token}"
            )
            if not can_process:
                raise CommandError(
                    f"La factura {invoice_id} no es pot recalcular: "
                    "cal que tingui lectures i contracte."
                )
            return

        if not can_process:
            raise CommandError(
                f"La factura {invoice_id} no es pot recalcular: "
                "cal que tingui lectures i contracte."
            )

        config_cache = _build_config_cache()
        disconnect_payment_signals()
        try:
            result = recalculate_invoice_preserving_identity(
                invoice_id,
                config_cache=config_cache,
                regenerate_pdf=regenerate_pdf,
            )
        except Exception as exc:
            raise CommandError(f"No s'ha pogut recalcular la factura {invoice_id}: {exc}") from exc
        finally:
            reconnect_payment_signals()

        old_total = result["old_total"]
        new_total = result["new_total"]
        total_msg = (
            f"total {old_total} -> {new_total}"
            if old_total != new_total
            else f"total {new_total} (sense canvi)"
        )
        payment_msg = "pagament actualitzat" if result["payment"] else "sense pagament"
        self.stdout.write(
            self.style.SUCCESS(
                f"  OK id={result['invoice_id']} "
                f"serie={result['invoice'].serie_final} issue_date={result['invoice'].issue_date} "
                f"{total_msg}, {payment_msg}"
            )
        )
