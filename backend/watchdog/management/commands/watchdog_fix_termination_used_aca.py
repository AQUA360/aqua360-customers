from django.core.management.base import BaseCommand, CommandError

from billing.models import Invoice
from watchdog.termination_used_aca import get_termination_used_aca_mismatches


class Command(BaseCommand):
    help = (
        "Posa a les factures i pressupostos de baixa el use_aca del contracte donat de baixa quan "
        "el used_aca desat és un altre. Recomanat quan el watchdog detecta "
        "'Factures de baixa amb used_aca erroni'. Revisa primer el --dry-run: si el use_aca del "
        "contracte s'ha canviat després de facturar, el valor desat és correcte i no s'ha de tocar; "
        "per això cal indicar les factures amb --ids, o --all per corregir-les totes."
    )

    def add_arguments(self, parser):
        """Opcions: --dry-run, --ids per triar factures i --all per corregir totes les detectades."""
        parser.add_argument('--dry-run', action='store_true', help='Mostra què es faria sense desar canvis')
        parser.add_argument('--ids', type=str, default='', help='IDs de factura separats per comes')
        parser.add_argument(
            '--all',
            action='store_true',
            help="Corregeix totes les factures detectades (revisa abans el --dry-run)",
        )

    def _parse_ids(self, value):
        """Converteix '1,2,3' en una llista d'enters; un valor no numèric és un error d'ús."""
        ids = []
        for part in value.split(','):
            part = part.strip()
            if not part:
                continue
            try:
                ids.append(int(part))
            except ValueError:
                raise CommandError(f"--ids: '{part}' no és un ID de factura vàlid")
        return ids

    def handle(self, *args, **options):
        """Llista les factures afectades i, si no és --dry-run, n'actualitza el used_aca."""
        dry_run = options['dry_run']
        ids = self._parse_ids(options['ids'])
        if not dry_run and not ids and not options['all']:
            raise CommandError(
                "Indica les factures a corregir amb --ids, o --all per corregir-les totes "
                "(revisa abans el llistat amb --dry-run)."
            )

        queryset = get_termination_used_aca_mismatches()
        if ids:
            queryset = queryset.filter(id__in=ids)

        rows = list(
            queryset.order_by('created_at', 'id').values_list(
                'id', 'serie_final', 'used_aca', 'contract_termination__contract__use_aca',
            )
        )
        if not rows:
            message = (
                "No hi ha factures seleccionades amb used_aca erroni."
                if ids else "No hi ha factures de baixa amb used_aca erroni."
            )
            self.stdout.write(self.style.SUCCESS(message))
            return

        prefix = '[DRY RUN] ' if dry_run else ''
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
