import calendar
from datetime import date, datetime, timedelta
from documentmanager.models import Document
from statistics.models import DailyDocument, DailyDocumentTemplate


def execute_available_report(available_report, report_data):
    from statistics.tasks import execute_report

    if not available_report or not available_report.function_name:
        raise ValueError("Available report has no function name")

    if available_report.section_id:
        report_data['type_id'] = available_report.section_id

    document_id, _filename = execute_report(
        available_report.function_name,
        report_data,
        skip_general_report=True,
    )
    return Document.objects.get(id=document_id)


def add_working_days(start_date, work_days):
    # Dies hàbils comuns a tota l'aplicació (també descompta els festius configurats).
    # Conserva el tipus d'entrada: si rep un datetime, en manté l'hora.
    import datetime as dt
    from coredata.utils.working_days import add_working_days as add_business_days
    result = add_business_days(start_date, work_days)
    if isinstance(start_date, dt.datetime):
        return dt.datetime.combine(result, start_date.timetz())
    return result


def compute_due_date(start_date, days_to_complete, is_work_days=False):
    days = days_to_complete if days_to_complete is not None else 2
    if days <= 0:
        return None
    if is_work_days:
        return add_working_days(start_date, days)
    return start_date + timedelta(days=days)


def _as_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def _previous_calendar_month(on_date):
    """Inclusive first/last day of the calendar month before on_date."""
    if on_date.month == 1:
        year, month = on_date.year - 1, 12
    else:
        year, month = on_date.year, on_date.month - 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _month_day_for(year, month, month_day):
    """Clamp month_day to the last valid day of that month (e.g. 31 → 28 in Feb)."""
    last_day = calendar.monthrange(year, month)[1]
    return min(max(int(month_day), 1), last_day)


def compute_period_range(template, end_date):
    """
    Inclusive date window covered by a document generated on end_date.
    - daily: [end, end]
    - weekly: 7 days ending on end_date (selected weekday)
    - monthly: previous calendar month relative to end_date
    - every_x_days: interval_days ending on end_date
    """
    end = _as_date(end_date)
    periodicity = getattr(template, 'periodicity', None) or DailyDocumentTemplate.PERIODICITY_DAILY

    if periodicity == DailyDocumentTemplate.PERIODICITY_WEEKLY:
        return end - timedelta(days=6), end

    if periodicity == DailyDocumentTemplate.PERIODICITY_MONTHLY:
        return _previous_calendar_month(end)

    if periodicity == DailyDocumentTemplate.PERIODICITY_EVERY_X_DAYS:
        interval = template.interval_days or 1
        if interval < 1:
            interval = 1
        return end - timedelta(days=interval - 1), end

    return end, end


def should_generate_on_date(template, on_date):
    """Whether this template should produce a document on on_date."""
    day = _as_date(on_date)
    periodicity = getattr(template, 'periodicity', None) or DailyDocumentTemplate.PERIODICITY_DAILY

    if periodicity == DailyDocumentTemplate.PERIODICITY_DAILY:
        return True

    if periodicity == DailyDocumentTemplate.PERIODICITY_WEEKLY:
        if template.weekday is None:
            return False
        return day.weekday() == int(template.weekday)

    if periodicity == DailyDocumentTemplate.PERIODICITY_MONTHLY:
        if template.month_day is None:
            return False
        return day.day == _month_day_for(day.year, day.month, template.month_day)

    if periodicity == DailyDocumentTemplate.PERIODICITY_EVERY_X_DAYS:
        interval = template.interval_days
        anchor = template.period_anchor_date
        if not interval or interval < 1 or not anchor:
            return False
        delta = (day - _as_date(anchor)).days
        return delta >= 0 and delta % interval == 0

    return False


def _format_period_label(start, end):
    if start == end:
        return start.strftime('%Y/%m/%d')
    return f"{start.strftime('%Y/%m/%d')} - {end.strftime('%Y/%m/%d')}"


def generate_daily_document(template, current_time, pending_status, cancelled_status=None):
    try:
        from statistics.tasks import ReportNoData
        from statistics.utils.submission_service import (
            get_submission_channel,
            submit_daily_document,
        )

        document_day = _as_date(current_time)
        if not should_generate_on_date(template, document_day):
            return None

        # if DailyDocument.objects.filter(template=template, document_date=document_day).exists():
        #     return None

        period_start, period_end = compute_period_range(template, document_day)
        period_label = _format_period_label(period_start, period_end)

        document = None
        error_message = None
        no_data_found = False
        try:
            report_data = {
                'start_date': period_start.strftime('%Y-%m-%d'),
                'end_date': period_end.strftime('%Y-%m-%d'),
                'name': f"{template.name} {period_label}",
            }
            document = execute_available_report(template.available_report, report_data)
        except ReportNoData:
            if not template.create_without_data:
                return None
            document = None
            no_data_found = True
        except Exception as e:
            document = None
            error_message = str(e)

        due_date = compute_due_date(
            document_day,
            template.days_to_complete,
            is_work_days=bool(template.is_work_days),
        )

        # No report file → cancelled; otherwise pending.
        status = cancelled_status if cancelled_status is not None and no_data_found else pending_status

        daily_document = DailyDocument.objects.create(
            token=f"{template.token}_{document_day.strftime('%Y%m%d')}",
            name=f"{template.name} {period_label}",
            document_date=document_day,
            period_start_date=period_start,
            period_end_date=period_end,
            due_date=due_date,
            status=status,
            template=template,
            document=document,
            creation_error=error_message,
            no_data_found=no_data_found,
        )

        # Auto-submit when the report file was generated successfully and a channel is configured.
        if document is not None and not no_data_found and not error_message:
            if get_submission_channel(daily_document):
                try:
                    submit_daily_document(daily_document)
                except Exception as e:
                    print(f"Error while submitting daily document {template.name}: {e}")

        return daily_document

    except Exception as e:
        print(f"Error while generating daily document {template.name}: {e}")
        return None
