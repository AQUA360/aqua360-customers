from django.core.management.base import BaseCommand, CommandError

from billing.utils.recalculate_invoice_service import delete_and_recalculate_invoice


class Command(BaseCommand):
    help = (
        "Esborra una prefactura i en genera una de nova. "
        "La factura resultant té un id diferent. Només accepta prefactures."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "invoice_id",
            type=int,
            help="Id de la prefactura a esborrar i regenerar",
        )

    def handle(self, *args, **options):
        invoice_id = options["invoice_id"]
        try:
            new_invoice = delete_and_recalculate_invoice(invoice_id)
        except Exception as exc:
            raise CommandError(f"Unable to recalculate invoice {invoice_id}: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Invoice {invoice_id} deleted and regenerated. New invoice id={new_invoice.id}"
            )
        )
