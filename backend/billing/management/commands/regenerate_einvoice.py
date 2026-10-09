from django.core.management.base import BaseCommand, CommandError

from billing.models import Invoice
from billing.views.epayment_document_generate_view import (
    get_einvoice_document,
    regenerate_einvoice_document,
)


class Command(BaseCommand):
    help = 'Regenera el XML de factura electrónica y sobrescribe el documento guardado en el programa.'

    def add_arguments(self, parser):
        parser.add_argument(
            'serie_final',
            nargs='+',
            help='Serie final de la factura (ej. FC/AAAAMM/000001). Se pueden indicar varias.',
        )

    def handle(self, *args, **options):
        series = [s.strip() for s in options['serie_final'] if s and s.strip()]
        if not series:
            raise CommandError('Debes indicar al menos una serie de factura.')

        errors = []
        for serie in series:
            invoice = Invoice.objects.filter(serie_final=serie, is_active=True).first()
            if not invoice:
                errors.append(f'Factura no encontrada: {serie}')
                continue

            previous_document = get_einvoice_document(invoice)
            document = regenerate_einvoice_document(invoice)

            if previous_document and document.id == previous_document.id:
                action = 'sobrescrito'
            elif previous_document:
                action = 'actualizado (nueva versión)'
            else:
                action = 'creado'

            self.stdout.write(
                self.style.SUCCESS(
                    f'{invoice.serie_final} (id {invoice.id}): XML {action} -> {document.document_name}'
                )
            )
            if document.location:
                self.stdout.write(f'  Ruta: {document.location}')

        if errors:
            for error in errors:
                self.stdout.write(self.style.ERROR(error))
            raise CommandError(f'Errores en {len(errors)} factura(s).')
