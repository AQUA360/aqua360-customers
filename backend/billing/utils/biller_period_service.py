"""Cicles de facturació d'un facturador (`Biller`).

Un facturador defineix els seus cicles amb `period_type` (mensual, bimestral,
trimestral...) i `initial_month` (mes en què comença el primer cicle de
l'any). Aquest mòdul resol, a partir d'una data, el cicle que la conté i els
següents, sense dependre d'un calendari fix de trimestres naturals.
"""

import calendar
from datetime import date

from django.utils import formats

PERIOD_TYPE_MONTHS = {
    'mensual': 1,
    'bimestral': 2,
    'trimestral': 3,
    'quadrimestral': 4,
    'semestral': 6,
    'anual': 12,
}

INITIAL_MONTH_NUMBER = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}

# Sufix del codi de període: `1T`, `2T`... (trimestral), `1B` (bimestral)...
PERIOD_CODE_SUFFIX = {
    'mensual': 'M',
    'bimestral': 'B',
    'trimestral': 'T',
    'quadrimestral': 'Q',
    'semestral': 'S',
    'anual': 'A',
}

# Valors per defecte del model `Biller`.
DEFAULT_PERIOD_TYPE = 'trimestral'
DEFAULT_INITIAL_MONTH = 'jan'


def _add_months(year, month, delta):
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def _month_name(year, month):
    """Nom del mes en l'idioma actiu, en minúscula."""
    return formats.date_format(date(year, month, 1), 'F').lower()


def cycle_containing(target_date, period_type=None, initial_month=None):
    """Cicle que conté `target_date`.

    Retorna un diccionari amb `year` (any d'inici), `period_code`,
    `month_from`, `year_from`, `month_to`, `year_to` i `months_label`.
    Un `period_type`/`initial_month` desconegut cau als valors per defecte
    del model `Biller`.
    """
    interval = PERIOD_TYPE_MONTHS.get(period_type)
    if interval is None:
        period_type = DEFAULT_PERIOD_TYPE
        interval = PERIOD_TYPE_MONTHS[period_type]
    initial = INITIAL_MONTH_NUMBER.get(initial_month) or INITIAL_MONTH_NUMBER[
        DEFAULT_INITIAL_MONTH
    ]

    position = ((target_date.month - initial) % 12) % interval
    year_from, month_from = _add_months(
        target_date.year, target_date.month, -position
    )
    year_to, month_to = _add_months(year_from, month_from, interval - 1)
    index = ((month_from - initial) % 12) // interval + 1

    if interval == 1:
        months_label = _month_name(year_from, month_from)
    else:
        months_label = (
            f"{_month_name(year_from, month_from)}-"
            f"{_month_name(year_to, month_to)}"
        )

    return {
        'year': year_from,
        'period_code': f"{index}{PERIOD_CODE_SUFFIX[period_type]}",
        'month_from': month_from,
        'year_from': year_from,
        'month_to': month_to,
        'year_to': year_to,
        'months_label': months_label,
        '_interval': interval,
    }


def cycle_dates(cycle):
    """`(data d'inici, data final)` d'un cicle retornat per `cycle_containing`."""
    start = date(cycle['year_from'], cycle['month_from'], 1)
    last_day = calendar.monthrange(cycle['year_to'], cycle['month_to'])[1]
    return start, date(cycle['year_to'], cycle['month_to'], last_day)


def previous_cycle(target_date, biller=None):
    """Cicle anterior al que conté `target_date` (l'últim cicle tancat)."""
    period_type = getattr(biller, 'period_type', None)
    initial_month = getattr(biller, 'initial_month', None)

    current = cycle_containing(target_date, period_type, initial_month)
    prev_year, prev_month = _add_months(
        current['year_from'], current['month_from'], -current['_interval']
    )
    return cycle_containing(date(prev_year, prev_month, 1), period_type, initial_month)


def current_and_next_cycles(target_date, biller=None):
    """`[cicle en curs, cicle següent]` per a `target_date`.

    Sense facturador s'apliquen els valors per defecte del model. El camp
    `is_current` marca el cicle que conté `target_date`.
    """
    period_type = getattr(biller, 'period_type', None)
    initial_month = getattr(biller, 'initial_month', None)

    current = cycle_containing(target_date, period_type, initial_month)
    next_year, next_month = _add_months(
        current['year_from'], current['month_from'], current['_interval']
    )
    following = cycle_containing(
        date(next_year, next_month, 1), period_type, initial_month
    )

    cycles = []
    for cycle, is_current in ((current, True), (following, False)):
        item = {k: v for k, v in cycle.items() if not k.startswith('_')}
        item['is_current'] = is_current
        cycles.append(item)
    return cycles
