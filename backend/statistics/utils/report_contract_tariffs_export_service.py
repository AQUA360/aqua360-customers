"""
Informe CSV (Celery) "Contractes: informació i PriceRate".

Reutilitza ContractFilter per aplicar filtres als contractes (igual que l'export 1),
i genera un CSV amb les tarifes (PriceRate) seleccionades segons el producte d'origen aigua (origin_id=1).
"""

import datetime

from django.http import HttpResponse

from contract.filters.contract_filter import ContractFilter
from contract.utils.contract_list_queryset import default_contract_list_queryset
from contract.utils.contract_tariffs_export import (
    build_contract_tariffs_export_csv_bytes,
)


def generate_contract_tariffs_export_report(request, black_fill=None, white_bold_font=None, task=None):
    from statistics.views.reports_views import save_report

    name = request.data.get("name", "") or "Contractes: informació i PriceRate"
    type_id = request.data.get("type_id", None)

    payload = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
    payload.pop("name", None)
    payload.pop("type_id", None)

    filterset = ContractFilter(
        data=payload,
        queryset=default_contract_list_queryset(),
    )

    filtered = filterset.qs
    body = build_contract_tariffs_export_csv_bytes(filtered)

    filename = f"contractes_informacio_i_pricerate_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    document_id = save_report(content=body, filename=filename, name=name, type_id=type_id)

    response = HttpResponse(body, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response, document_id, filename

