"""
Repara les lectures generades pel canvi de comptador automàtic via ordre de
treball (origen antic 'order_change_meter').

Aquestes lectures es desaven amb calculated_value = valor de lectura (en lloc
del consum respecte de la lectura anterior del mateix comptador) i, com que la
lectura de tancament (is_close) no passa per la correcció del lot de lectures,
el consum erroni s'acabava facturant.

Per defecte només informa (dry-run). Amb --apply desa els canvis:
  backend/.venv/bin/python manage.py fix_order_change_meter_readings
  backend/.venv/bin/python manage.py fix_order_change_meter_readings --apply
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from billing.models import EstimatedBagMovement, Reading
from service.services.meter_change_service import (
    LEGACY_ORDER_CHANGE_METER_ORIGIN,
    METER_CHANGE_ORIGIN,
    add_to_estimated_bag,
    to_decimal as _dec,
)


class Command(BaseCommand):
    help = (
        "Recalcula calculated_value i real_consumption de les lectures del canvi "
        "de comptador via ordre de treball i n'unifica l'origen. Dry-run per defecte."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help="Desa els canvis. Sense aquest paràmetre només es mostra què es faria.",
        )
        parser.add_argument(
            '--contract', type=int, default=None,
            help="Limita la revisió a un sol contracte (ID).",
        )

    # ------------------------------------------------------------------ #
    # Càlcul
    # ------------------------------------------------------------------ #
    def _previous_same_meter(self, reading):
        """
        Lectura anterior del mateix comptador, contracte i punt de subministrament,
        creada abans que aquesta (mateix dia: id menor).
        """
        return (
            Reading.objects
            .filter(
                contract_id=reading.contract_id,
                supply_point_id=reading.supply_point_id,
                meter_id=reading.meter_id,
                is_control=False,
                is_active=True,
            )
            .filter(
                Q(reading_date__lt=reading.reading_date)
                | Q(reading_date=reading.reading_date, id__lt=reading.id)
            )
            .exclude(id=reading.id)
            .order_by('-reading_date', '-id')
            .first()
        )

    def _expected_consumption(self, reading):
        """
        Retorna (consum esperat, lectura de referència).

        Si previous_reading és del mateix comptador s'hi calcula directament:
        cobreix també el cas en què la lectura anterior es va fusionar (marcada
        com a control) i previous_reading apunta a la lectura d'abans.
        Si no (p. ex. lectura inicial del comptador nou enllaçada amb el
        tancament del vell) es busca la lectura anterior del mateix comptador;
        si no n'hi ha, el consum és 0.
        """
        previous = reading.previous_reading
        # Una lectura de control fusionada continua sent vàlida si és activa.
        if not previous or previous.meter_id != reading.meter_id or not previous.is_active:
            previous = self._previous_same_meter(reading)
        if not previous:
            return Decimal(0), None
        expected = max(Decimal(0), _dec(reading.reading_value) - _dec(previous.reading_value))
        return expected, previous

    # ------------------------------------------------------------------ #
    # Execució
    # ------------------------------------------------------------------ #
    def handle(self, *args, **options):
        apply_changes = options['apply']
        mode = 'APPLY' if apply_changes else 'DRY-RUN'
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"[{mode}] Revisant lectures amb origin={LEGACY_ORDER_CHANGE_METER_ORIGIN!r}"
        ))

        readings = (
            Reading.objects
            .filter(origin=LEGACY_ORDER_CHANGE_METER_ORIGIN)
            .select_related('meter', 'previous_reading')
            .prefetch_related('invoices')
            .order_by('reading_date', 'id')
        )
        if options['contract']:
            readings = readings.filter(contract_id=options['contract'])

        stats = {
            'inspected': 0, 'fixed': 0, 'ok': 0, 'with_invoice': 0,
            'bag_adjusted': 0, 'bag_missing': 0, 'origin_renamed': 0,
        }
        invoice_warnings = []

        with transaction.atomic():
            for reading in readings:
                stats['inspected'] += 1
                self._process(reading, stats, invoice_warnings, apply_changes)

            if not apply_changes:
                transaction.set_rollback(True)

        self._print_summary(stats, invoice_warnings, apply_changes)

    def _process(self, reading, stats, invoice_warnings, apply_changes):
        expected, previous = self._expected_consumption(reading)

        old_calc = _dec(reading.calculated_value)
        old_real = _dec(reading.real_consumption)
        old_used = _dec(reading.estimated_used)

        new_used = min(old_used, expected)
        excess_estimated = old_used - new_used
        new_real = expected - new_used

        needs_fix = old_calc != expected or old_real != new_real or excess_estimated > 0

        prev_info = (
            f"prev #{previous.id} ({previous.reading_date}, value={previous.reading_value})"
            if previous else "prev: none (new meter -> 0)"
        )
        header = (
            f"Reading #{reading.id} | contract={reading.contract_id} "
            f"| supply_point={reading.supply_point_id} | meter={getattr(reading.meter, 'code', None)} "
            f"| date={reading.reading_date} | value={reading.reading_value} "
            f"| is_close={reading.is_close} | {prev_info}"
        )

        if needs_fix:
            stats['fixed'] += 1
            self.stdout.write(self.style.WARNING(f"FIX  {header}"))
            self.stdout.write(
                f"     calculated_value: {old_calc} -> {expected} | "
                f"real_consumption: {old_real} -> {new_real} | "
                f"estimated_used: {old_used} -> {new_used}"
            )
        else:
            stats['ok'] += 1
            self.stdout.write(f"OK   {header} | calculated_value={old_calc} real_consumption={old_real}")

        invoices = list(reading.invoices.all())
        if invoices:
            stats['with_invoice'] += 1
            numbers = ', '.join(f"{inv.number or '-'} (#{inv.id})" for inv in invoices)
            level = self.style.ERROR if needs_fix else self.style.NOTICE
            self.stdout.write(level(
                f"     WARNING: reading #{reading.id} has related invoice(s): {numbers}"
                + (" -> invoiced consumption must be reviewed manually" if needs_fix else "")
            ))
            if needs_fix:
                invoice_warnings.append((reading.id, numbers))

        if needs_fix:
            reading.calculated_value = expected
            reading.real_consumption = new_real
            reading.estimated_used = new_used if new_used > 0 else None
            if excess_estimated > 0:
                self._return_estimated(reading, excess_estimated, stats)

        if reading.origin != METER_CHANGE_ORIGIN:
            stats['origin_renamed'] += 1
            self.stdout.write(f"     origin: {reading.origin!r} -> {METER_CHANGE_ORIGIN!r}")
            reading.origin = METER_CHANGE_ORIGIN

        reading.save(update_fields=[
            'calculated_value', 'real_consumption', 'estimated_used', 'origin',
        ])

    def _return_estimated(self, reading, amount, stats):
        """Retorna a la bossa d'estimades el consum estimat descomptat de més."""
        movement = (
            EstimatedBagMovement.objects
            .filter(reading=reading, is_positive=False, is_active=True)
            .select_related('estimated_bag')
            .first()
        )
        if not movement:
            stats['bag_missing'] += 1
            self.stdout.write(self.style.ERROR(
                f"     WARNING: {amount} m3 of estimated consumption should be returned "
                f"but no bag movement was found for reading #{reading.id} -> review manually"
            ))
            return

        bag = movement.estimated_bag
        EstimatedBagMovement.objects.create(
            amount=amount,
            estimated_bag=bag,
            reading=reading,
            movement_date=reading.reading_date,
            is_positive=True,
        )
        old_total = _dec(bag.total_consumption)
        add_to_estimated_bag(bag.id, amount)
        bag.refresh_from_db(fields=['total_consumption'])
        stats['bag_adjusted'] += 1
        self.stdout.write(
            f"     estimated bag #{bag.id}: returned {amount} m3 "
            f"(total {old_total} -> {bag.total_consumption})"
        )

    def _print_summary(self, stats, invoice_warnings, apply_changes):
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Summary'))
        self.stdout.write(f"  Inspected readings:            {stats['inspected']}")
        self.stdout.write(f"  Already correct:               {stats['ok']}")
        self.stdout.write(f"  Recalculated:                  {stats['fixed']}")
        self.stdout.write(f"  With related invoice:          {stats['with_invoice']}")
        self.stdout.write(f"  Estimated bag returns:         {stats['bag_adjusted']}")
        self.stdout.write(f"  Bag returns needing review:    {stats['bag_missing']}")
        self.stdout.write(f"  Origin renamed:                {stats['origin_renamed']}")

        if invoice_warnings:
            self.stdout.write(self.style.ERROR(
                f"  {len(invoice_warnings)} recalculated reading(s) already invoiced:"
            ))
            for reading_id, numbers in invoice_warnings:
                self.stdout.write(self.style.ERROR(f"    - reading #{reading_id}: {numbers}"))

        if apply_changes:
            self.stdout.write(self.style.SUCCESS("Changes saved."))
        else:
            self.stdout.write(self.style.NOTICE(
                "DRY-RUN: nothing was saved. Run again with --apply to persist the changes."
            ))
