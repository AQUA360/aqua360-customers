"""
Informe CSV (Celery): mateixa lògica que docs/sql/vw_contract_invoice_reading_summary.sql.
"""
import datetime

from django.http import HttpResponse

from contract.utils.contract_invoice_reading_summary_export import (
    build_invoice_reading_summary_csv_bytes,
)


def generate_contract_invoice_reading_summary_report(
    request, black_fill=None, white_bold_font=None, task=None
):
    from statistics.views.reports_views import save_report

    name = request.data.get('name', '') or 'Resum contractes factura i lectures'
    type_id = request.data.get('type_id', None)

    body = build_invoice_reading_summary_csv_bytes()
    filename = (
        f"contract_invoice_reading_summary_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )

    document_id = save_report(content=body, filename=filename, name=name, type_id=type_id)

    response = HttpResponse(body, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response, document_id, filename
