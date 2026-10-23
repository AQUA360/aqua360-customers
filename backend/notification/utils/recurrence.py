"""
Generació de les ocurrències de les tasques recurrents.

Les ocurrències es materialitzen com a CalendarTask amb `recurrence` informat, fins
a `HORIZON_DAYS` dies vista. La tasca diària `generate_recurring_tasks` va allargant
aquest horitzó, de manera que el calendari sempre té les properes ocurrències sense
haver-les de calcular al vol a cada consulta.
"""
import datetime
import uuid

from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, YEARLY
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from notification.models import CalendarTask, CalendarTaskRecurrence

HORIZON_DAYS = 90

_FREQUENCIES = {
    CalendarTaskRecurrence.FREQUENCY_DAILY: DAILY,
    CalendarTaskRecurrence.FREQUENCY_WEEKLY: WEEKLY,
    CalendarTaskRecurrence.FREQUENCY_MONTHLY: MONTHLY,
    CalendarTaskRecurrence.FREQUENCY_YEARLY: YEARLY,
}


def occurrence_dates(recurrence, date_from, date_to):
    """Dates de la regla entre `date_from` i `date_to` (incloses)."""
    if date_from > date_to:
        return []
    kwargs = {
        'dtstart': datetime.datetime.combine(recurrence.start_date, datetime.time()),
        'interval': max(recurrence.interval or 1, 1),
    }
    start = recurrence.start_date
    if recurrence.frequency == CalendarTaskRecurrence.FREQUENCY_WEEKLY and recurrence.weekdays:
        kwargs['byweekday'] = sorted({int(d) for d in recurrence.weekdays if 0 <= int(d) <= 6})
    elif recurrence.frequency in (CalendarTaskRecurrence.FREQUENCY_MONTHLY, CalendarTaskRecurrence.FREQUENCY_YEARLY) and start.day > 28:
        # Dia 29-31: els mesos que no el tenen fan servir l'últim dia del mes, en
        # lloc de saltar-se (que és el que fa rrule per defecte).
        kwargs['bymonthday'] = tuple(range(28, start.day + 1))
        kwargs['bysetpos'] = -1
        if recurrence.frequency == CalendarTaskRecurrence.FREQUENCY_YEARLY:
            kwargs['bymonth'] = start.month
    until = date_to if not recurrence.end_date else min(date_to, recurrence.end_date)
    kwargs['until'] = datetime.datetime.combine(until, datetime.time())

    rule = rrule(_FREQUENCIES[recurrence.frequency], **kwargs)
    first = datetime.datetime.combine(date_from, datetime.time())
    return [d.date() for d in rule if d >= first]


def _task_from_template(recurrence, set_date):
    """Build an unsaved task from the recurrence template for the given date."""
    return CalendarTask(
        token=str(uuid.uuid4()),
        name=recurrence.name,
        description=recurrence.description,
        color=recurrence.color,
        user=recurrence.user,
        time=recurrence.time,
        set_date=set_date,
        recurrence=recurrence,
    )


def generate_occurrences(recurrence, until=None):
    """
    Crea les ocurrències que faltin fins a `until` (per defecte, avui + HORIZON_DAYS).
    Retorna el nombre de tasques creades.
    """
    if not recurrence.is_active:
        return 0
    if not until:
        # Si la sèrie comença més enllà de l'horitzó (p. ex. una anual d'aquí a uns mesos),
        # es genera almenys fins a la primera setmana de la sèrie perquè tingui la primera ocurrència.
        until = max(
            timezone.localdate() + datetime.timedelta(days=HORIZON_DAYS),
            recurrence.start_date + datetime.timedelta(days=7),
        )
    date_from = recurrence.start_date
    if recurrence.generated_until:
        date_from = max(date_from, recurrence.generated_until + datetime.timedelta(days=1))

    dates = occurrence_dates(recurrence, date_from, until)
    existing = set(
        recurrence.tasks.filter(set_date__in=dates).values_list('set_date', flat=True)
    )
    tasks = [_task_from_template(recurrence, d) for d in dates if d not in existing]
    with transaction.atomic():
        CalendarTask.objects.bulk_create(tasks)
        recurrence.generated_until = max(until, recurrence.generated_until) if recurrence.generated_until else until
        recurrence.save(update_fields=['generated_until', 'updated_at'])
    return len(tasks)


def regenerate_from(recurrence, date_from, tasks_filter=None):
    """
    Després de canviar la regla: esborra les ocurrències pendents a partir de
    `date_from` i les torna a generar amb la regla nova. Les ja fetes es conserven,
    i amb `tasks_filter` només es toquen les ocurrències que hi compleixen (les que
    l'usuari pot veure).
    """
    with transaction.atomic():
        recurrence.tasks.filter(tasks_filter or Q(), set_date__gte=date_from, task_done=False).delete()
        recurrence.generated_until = date_from - datetime.timedelta(days=1)
        recurrence.save(update_fields=['generated_until', 'updated_at'])
    return generate_occurrences(recurrence)


def stop_from(recurrence, date_from, tasks_filter=None):
    """Atura la sèrie: esborra les ocurrències pendents a partir de `date_from`."""
    with transaction.atomic():
        recurrence.tasks.filter(tasks_filter or Q(), set_date__gte=date_from, task_done=False).delete()
        recurrence.end_date = date_from - datetime.timedelta(days=1)
        if recurrence.end_date < recurrence.start_date:
            recurrence.is_active = False
        recurrence.save(update_fields=['end_date', 'is_active', 'updated_at'])
