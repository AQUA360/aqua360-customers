from django.core.management.base import BaseCommand
from django.db import transaction

from billing.models import Invoice
from watchdog.termination_used_aca import get_termination_used_aca_mismatches


class Command(BaseCommand):
    help = (
        "Posa a les factures i pressupostos de baixa el use_aca del contracte donat de baixa quan "
        "el used_aca desat és un altre. Recomanat quan el watchdog detecta "
        "'Factures de baixa amb used_aca erroni'. Revisa primer el --dry-run: si el use_aca del "
        "contracte s'ha canviat després de facturar, limita la correcció amb --ids."
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Mostra què es faria sense desar canvis')
        parser.add_argument(
            '--ids',
            type=str,
            default='',
            help='IDs de factura separats per comes; per defecte, totes les detectades',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        queryset = get_termination_used_aca_mismatches()
        ids = [int(value) for value in options['ids'].split(',') if value.strip()]
        if ids:
            queryset = queryset.filter(id__in=ids)

        rows = list(
            queryset.order_by('created_at', 'id').values_list(
                'id', 'serie_final', 'used_aca', 'contract_termination__contract__use_aca',
            )
        )
        if not rows:
            self.stdout.write(self.style.SUCCESS("No hi ha factures de baixa amb used_aca erroni."))
            return

        prefix = '[DRY RUN] ' if dry_run else ''
        with transaction.atomic():
            for invoice_id, serie_final, used_aca, expected in rows:
                new_value = expected or None
                self.stdout.write(
                    f"{prefix}Factura ID {invoice_id} ({serie_final or '-'}): used_aca {used_aca!r} -> {new_value!r}"
                )
                if not dry_run:
                    # update() per no disparar senyals ni tocar updated_at d'una factura emesa
                    Invoice.objects.filter(id=invoice_id).update(used_aca=new_value)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f"{prefix}Factures corregides: {len(rows)}"))
        self.stdout.write(
            self.style.WARNING(
                "Si el trimestre d'alguna factura ja s'ha presentat a l'ACA, cal valorar "
                "una declaració complementària."
            )
        )
