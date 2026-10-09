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


def generate_daily_document(template, current_time, pending_status):
    try:
        document = None
        error_message = None
        try:
            date_str = current_time.strftime('%Y-%m-%d')
            report_data = {
                'start_date': date_str,
                'end_date': date_str,
                'name': f"{template.name} {current_time.strftime('%Y/%m/%d')}",
            }
            document = execute_available_report(template.available_report, report_data)
        except Exception as e:
            document = None
            error_message = str(e)
        
        due_date = current_time.date() + timedelta(days=template.days_to_complete or 2) if template.days_to_complete > 0 else None

        DailyDocument.objects.create(
            token=f"{template.token}_{current_time.strftime('%Y%m%d')}",
            name=f"{template.name} {current_time.strftime('%Y/%m/%d')}",
            document_date=current_time.date(),
            due_date=due_date,
            status=pending_status,
            template=template,
            document=document,
            creation_error=error_message
        )

    except Exception as e:
        print(f"Error while generating daily document {template.name}: {e}")
