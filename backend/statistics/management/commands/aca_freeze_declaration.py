"""Congela el mes ja presentat d'una Declaració ACA (A1) per a una explotació.

Sense --commit només mostra què es congelaria. Amb --xlsx es fa servir l'informe presentat: el full de
factures (les factures declarades encara que després s'hagin anul·lat o desactivat) i els totals del
resum de l'explotació, que les línies congelades han de reproduir al cèntim.
"""
import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from service.models import Exploitation
from statistics.models import AcaDeclaration
from statistics.utils.aca_declaration_service import build_aca_declaration


def _read_presented_xlsx(path, exploitation, invoices_sheet=None, summary_sheet=None):
    import openpyxl

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    summary = workbook[summary_sheet] if summary_sheet else workbook.worksheets[0]
    invoices = workbook[invoices_sheet] if invoices_sheet else workbook.worksheets[1]

    rows = {row[0]: row[1:] for row in summary.iter_rows(values_only=True) if row and row[0]}
    names = [str(name or '').strip().upper() for name in rows.get('Població/Explotació', ())]
    if exploitation.name.strip().upper() not in names:
        raise CommandError(f"El resum de {path} no té la columna de l'explotació {exploitation.name}")
    column = names.index(exploitation.name.strip().upper())

    def amount(title):
        return Decimal(str(rows[title][column] or 0)).quantize(Decimal('0.01'))

    numbers = [row[0] for row in invoices.iter_rows(min_row=2, values_only=True) if row and row[0]]
    return amount('Import part fixa'), amount('Import part variable'), numbers


class Command(BaseCommand):
    help = "Congela les línies de cànon declarades en un mes ja presentat de la Declaració ACA (A1)"

    def add_arguments(self, parser):
        parser.add_argument('--exploitation', required=True, help="Id o codi INE de l'explotació")
        parser.add_argument('--month', required=True, help='Mes presentat, AAAA-MM')
        parser.add_argument('--presented-at', help="Moment de l'informe presentat (ISO); per defecte, ara")
        parser.add_argument('--xlsx', help='Informe A1 presentat')
        parser.add_argument('--invoices-sheet', help="Full de factures de l'informe (per defecte, el segon)")
        parser.add_argument('--summary-sheet', help="Full de resum de l'informe (per defecte, el primer)")
        parser.add_argument('--fixed', help='Import de part fixa presentat (si no hi ha --xlsx)')
        parser.add_argument('--variable', help='Import de part variable presentat (si no hi ha --xlsx)')
        parser.add_argument('--include', nargs='*', default=[], help='Números de factura declarats a més')
        parser.add_argument('--exclude', nargs='*', default=[], help='Números de factura no declarats')
        parser.add_argument('--force', action='store_true', help='Desa encara que els totals no quadrin')
        parser.add_argument('--commit', action='store_true', help='Desa la declaració (si no, només la mostra)')

    def handle(self, *args, **options):
        reference = options['exploitation']
        exploitation = Exploitation.objects.filter(id=int(reference)).first() if reference.isdigit() else None
        if exploitation is None:
            exploitation = Exploitation.objects.filter(code=reference).first()
        if exploitation is None:
            raise CommandError(f"No hi ha cap explotació {reference}")
        try:
            year, month = (int(part) for part in options['month'].split('-'))
            datetime.date(year, month, 1)
        except ValueError:
            raise CommandError('--month ha de ser AAAA-MM')
        presented_at = timezone.now()
        if options['presented_at']:
            presented_at = datetime.datetime.fromisoformat(options['presented_at'])
            if timezone.is_naive(presented_at):
                presented_at = timezone.make_aware(presented_at)

        listed, expected_fixed, expected_variable = [], None, None
        if options['xlsx']:
            expected_fixed, expected_variable, listed = _read_presented_xlsx(
                options['xlsx'], exploitation, options['invoices_sheet'], options['summary_sheet'],
            )
        if options['fixed'] is not None:
            expected_fixed = Decimal(options['fixed'])
        if options['variable'] is not None:
            expected_variable = Decimal(options['variable'])

        result = build_aca_declaration(
            exploitation, year, month, presented_at, listed, options['include'], options['exclude'],
        )
        self.stdout.write(
            f"{exploitation.name} {year}-{month:02d}: {len(result.invoice_ids)} factures, "
            f"{len(result.line_ids)} línies, part fixa {result.fixed_amount}, part variable {result.variable_amount}"
        )
        if result.unresolved:
            self.stdout.write(f"Factures no trobades ({len(result.unresolved)}): {', '.join(result.unresolved)}")
        if result.inactive_line_invoices:
            self.stdout.write(f"Factures amb les línies de cànon desactivades: {len(result.inactive_line_invoices)}")

        matches = True
        if expected_fixed is not None or expected_variable is not None:
            diff_fixed = result.fixed_amount - (expected_fixed if expected_fixed is not None else result.fixed_amount)
            diff_variable = result.variable_amount - (expected_variable if expected_variable is not None else result.variable_amount)
            matches = not diff_fixed and not diff_variable
            self.stdout.write(
                f"Presentat: part fixa {expected_fixed}, part variable {expected_variable}. "
                f"Diferència: part fixa {diff_fixed}, part variable {diff_variable}"
            )
        if not options['commit']:
            self.stdout.write("Sense --commit no es desa res")
            return
        if not matches and not options['force']:
            raise CommandError("Els totals no quadren amb els presentats: no es desa (--force per desar-ho igualment)")

        with transaction.atomic():
            declaration, _created = AcaDeclaration.objects.update_or_create(
                exploitation=exploitation, year=year, month=month,
                defaults={
                    'presented_at': presented_at,
                    'fixed_amount': expected_fixed if expected_fixed is not None else result.fixed_amount,
                    'variable_amount': expected_variable if expected_variable is not None else result.variable_amount,
                    'source': (options['xlsx'] or 'estat actual').rsplit('/', 1)[-1][:255],
                },
            )
            declaration.line_items.set(result.line_ids)
        self.stdout.write(self.style.SUCCESS(f"Declaració {declaration} congelada"))
