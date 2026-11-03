"""
Càlcul de dies hàbils: de dilluns a divendres, sense els festius configurats
(Holiday). Els festius sense explotació s'apliquen a totes; els d'una explotació,
només quan es calcula per a aquella explotació.
"""
import datetime

from django.db.models import Q


def get_holidays(start_date, end_date, exploitation=None):
    """Return the set of holiday dates between both dates (inclusive)."""
    from coredata.models import Holiday

    scope = Q(exploitation__isnull=True)
    if exploitation is not None:
        scope |= Q(exploitation=exploitation)
    return set(
        Holiday.objects.filter(scope, date__gte=start_date, date__lte=end_date).values_list('date', flat=True)
    )


def _as_date(value):
    return value.date() if isinstance(value, datetime.datetime) else value


def add_working_days(start_date, work_days, exploitation=None):
    """Data resultant de sumar work_days dies hàbils a start_date (sense comptar-la)."""
    start_date = _as_date(start_date)
    # Marge ampli per carregar els festius d'un sol cop
    holidays = get_holidays(start_date, start_date + datetime.timedelta(days=work_days * 2 + 31), exploitation)
    current_date = start_date
    added_days = 0
    while added_days < work_days:
        current_date += datetime.timedelta(days=1)
        if current_date.weekday() < 5 and current_date not in holidays:
            added_days += 1
    return current_date


def subtract_working_days(start_date, work_days, exploitation=None):
    """Data resultant de restar work_days dies hàbils a start_date."""
    start_date = _as_date(start_date)
    holidays = get_holidays(start_date - datetime.timedelta(days=work_days * 2 + 31), start_date, exploitation)
    current_date = start_date
    removed_days = 0
    while removed_days < work_days:
        current_date -= datetime.timedelta(days=1)
        if current_date.weekday() < 5 and current_date not in holidays:
            removed_days += 1
    return current_date


def count_working_days(start_date, end_date, exploitation=None):
    """Dies hàbils posteriors a start_date fins a end_date (inclòs)."""
    start_date, end_date = _as_date(start_date), _as_date(end_date)
    if end_date <= start_date:
        return 0
    holidays = get_holidays(start_date, end_date, exploitation)
    count = 0
    current_date = start_date
    while current_date < end_date:
        current_date += datetime.timedelta(days=1)
        if current_date.weekday() < 5 and current_date not in holidays:
            count += 1
    return count
