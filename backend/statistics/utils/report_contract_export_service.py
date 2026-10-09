"""
Informe CSV de contractes (async via Celery): reutilitza contract.utils.contract_csv_export.
"""
import datetime

from django.http import HttpResponse

from contract.filters.contract_filter import ContractFilter
from contract.utils.contract_csv_export import build_contract_export_csv_bytes
from contract.utils.contract_list_queryset import default_contract_list_queryset


def _filter_payload(request_data):
    if hasattr(request_data, 'copy'):
        raw = request_data.copy()
    else:
        raw = dict(request_data)
    raw.pop('name', None)
    raw.pop('type_id', None)
    return raw


def generate_contracts_export_report(request, black_fill=None, white_bold_font=None, task=None):
    from statistics.views.reports_views import save_report

    name = request.data.get('name', '') or 'Exportació contractes'
    type_id = request.data.get('type_id', None)

    filterset = ContractFilter(
        data=_filter_payload(request.data),
        queryset=default_contract_list_queryset(),
    )
    filtered = filterset.qs

    body = build_contract_export_csv_bytes(filtered)
    filename = f"contractes_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    document_id = save_report(content=body, filename=filename, name=name, type_id=type_id)

    response = HttpResponse(body, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response, document_id, filename
