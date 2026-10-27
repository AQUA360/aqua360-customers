from datetime import timedelta
from documentmanager.models import Document
from statistics.models import DailyDocument


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
    # Dies hàbils comuns a tota l'aplicació (també descompta els festius configurats)
    from coredata.utils.working_days import add_working_days as add_business_days
    return add_business_days(start_date, work_days)


def compute_due_date(start_date, days_to_complete, is_work_days=False):
    days = days_to_complete if days_to_complete is not None else 2
    if days <= 0:
        return None
    if is_work_days:
        return add_working_days(start_date, days)
    return start_date + timedelta(days=days)


def generate_daily_document(template, current_time, pending_status):
    try:
        from statistics.tasks import ReportNoData

        document = None
        error_message = None
        no_data_found = False
        try:
            date_str = current_time.strftime('%Y-%m-%d')
            report_data = {
                'start_date': date_str,
                'end_date': date_str,
                'name': f"{template.name} {current_time.strftime('%Y/%m/%d')}",
            }
            document = execute_available_report(template.available_report, report_data)
        except ReportNoData:
            document = None
            no_data_found = True
        except Exception as e:
            document = None
            error_message = str(e)

        due_date = compute_due_date(
            current_time.date(),
            template.days_to_complete,
            is_work_days=bool(template.is_work_days),
        )

        DailyDocument.objects.create(
            token=f"{template.token}_{current_time.strftime('%Y%m%d')}",
            name=f"{template.name} {current_time.strftime('%Y/%m/%d')}",
            document_date=current_time.date(),
            due_date=due_date,
            status=pending_status,
            template=template,
            document=document,
            creation_error=error_message,
            no_data_found=no_data_found,
        )

    except Exception as e:
        print(f"Error while generating daily document {template.name}: {e}")
