from django.core.management.base import BaseCommand, CommandError

from billing.utils.recalculate_invoice_service import recalculate_invoice_smart


class Command(BaseCommand):
    help = "Recalculates a single invoice and replaces it with a regenerated one, swapping control readings with modifications if available."

    def add_arguments(self, parser):
        parser.add_argument(
            "invoice_id",
            type=int,
            help="Invoice id to recalculate",
        )

    def handle(self, *args, **options):
        invoice_id = options["invoice_id"]
        try:
            new_invoice = recalculate_invoice_smart(invoice_id)
        except Exception as exc:
            raise CommandError(f"Unable to recalculate invoice {invoice_id}: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Invoice {invoice_id} recalculated successfully with smart reading swap. New invoice id={new_invoice.id}"
            )
        )
