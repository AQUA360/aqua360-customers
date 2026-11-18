"""Omple SupplyPointMeterHistory a partir dels logs de canvi de comptador
que ja existeixen (LogSupplyPointChange amb action='meter').

- La data del canvi surt de la lectura de canvi de comptador del punt (és la
  data real; el log es pot haver registrat dies o mesos després). Si no n'hi
  ha, es fa servir la data del log.
- Les lectures antiga/nova surten de les mateixes lectures de canvi.
- La procedència es dedueix de l'origin d'aquestes lectures.
- Els logs que ja tenen fila a l'historial (canvis fets amb el codi nou, que
  escriu les dues coses alhora) se salten.
"""
import datetime

from django.core.management.color import color_style

from billing.models import Reading
from logger.models import LogSupplyPointChange
from service.models import Meter, SupplyPointMeterHistory

style = color_style()

# origin de les lectures de canvi de comptador -> SupplyPointMeterHistory.source
ORIGIN_SOURCE = {
    'Canvi de comptador': 'ui',
    'Cambio de contador': 'ui',
    'Meter change': 'ui',
    'Canvi de comptador (i)': 'bulk',
    'bulk_change_meter': 'bulk',
    'order_change_meter': 'order',
    'Ordre canvi comptador': 'order',
}
# Marge per reconèixer la fila d'historial que el codi nou ja ha creat amb el log.
SAME_CHANGE_WINDOW = datetime.timedelta(minutes=1)


def _already_recorded(log):
    return SupplyPointMeterHistory.objects.filter(
        supply_point_id=log.supply_point_id,
        old_meter_id=log.previous_related_id,
        new_meter_id=log.current_related_id,
        created_at__gte=log.timestamp - SAME_CHANGE_WINDOW,
        created_at__lte=log.timestamp + SAME_CHANGE_WINDOW,
    ).exists()


def _change_reading(supply_point_id, meter_id, is_close, until_date, on_date=None):
    """Lectura de canvi de comptador més recent d'aquell comptador al punt."""
    if not meter_id:
        return None
    readings = Reading.objects.filter(
        supply_point_id=supply_point_id,
        meter_id=meter_id,
        origin__in=ORIGIN_SOURCE.keys(),
        is_close=is_close,
    )
    if on_date:
        readings = readings.filter(reading_date=on_date)
    else:
        readings = readings.filter(reading_date__lte=until_date)
    return readings.order_by('-reading_date', '-id').first()


def run():
    logs = (
        LogSupplyPointChange.objects
        .filter(action='meter', supply_point__isnull=False)
        .order_by('timestamp', 'id')
    )
    existing_meter_ids = set(Meter.objects.values_list('id', flat=True))

    to_create = []
    skipped = 0
    for log in logs:
        if _already_recorded(log):
            skipped += 1
            continue

        log_date = log.timestamp.date()
        old_meter_id = log.previous_related_id if log.previous_related_id in existing_meter_ids else None
        new_meter_id = log.current_related_id if log.current_related_id in existing_meter_ids else None

        new_reading = _change_reading(log.supply_point_id, new_meter_id, False, log_date)
        change_date = new_reading.reading_date if new_reading else None
        old_reading = _change_reading(
            log.supply_point_id, old_meter_id, True, log_date, on_date=change_date,
        )
        if change_date is None and old_reading:
            change_date = old_reading.reading_date

        origin = (new_reading or old_reading).origin if (new_reading or old_reading) else None

        observation = log.observation
        missing = [
            f"{label} {code} (id {related_id}) ja no existeix"
            for label, code, related_id, kept in (
                ('Comptador antic', log.previous_value, log.previous_related_id, old_meter_id),
                ('Comptador nou', log.current_value, log.current_related_id, new_meter_id),
            )
            if related_id and not kept
        ]
        if missing:
            observation = '; '.join(filter(None, [observation, *missing]))

        to_create.append(SupplyPointMeterHistory(
            supply_point_id=log.supply_point_id,
            old_meter_id=old_meter_id,
            new_meter_id=new_meter_id,
            change_date=change_date or log_date,
            old_reading=old_reading.reading_value if old_reading else None,
            new_reading=new_reading.reading_value if new_reading else None,
            source=ORIGIN_SOURCE.get(origin, 'other'),
            user_id=log.user_id,
            observation=observation,
        ))

    SupplyPointMeterHistory.objects.bulk_create(to_create, batch_size=500)
    print(style.SUCCESS(
        f"SupplyPointMeterHistory des de logs: {len(to_create)} creats, {skipped} ja existien"
    ))
