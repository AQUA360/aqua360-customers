"""
Informe CSV (Celery): baixes de contracte amb darrera lectura i darrera factura.
Equivalent funcional a la vista vw_contract_termination_last_reading_invoice,
però resolt via ORM.
"""

import csv
import datetime
from io import StringIO

from django.db.models import OuterRef, Subquery, Q
from django.http import HttpResponse
from django.utils.translation import gettext as _

from billing.models import Invoice, Reading
from contract.models import ContractTerminationRequest
from statistics.utils.report_filters import get_multi_ids


def _headers():
    return [
        _('ID contracte'),
        _('Token contracte'),
        _('ID sol. baixa'),
        _('Token estat sol. baixa'),
        _('Data creacio baixa'),
        _('ID darrera lectura'),
        _('Data darrera lectura'),
        _('Origen darrera lectura'),
        _('ID darrera factura'),
        _('Token darrera factura'),
        _('Data darrera factura'),
    ]


def _fmt_date(value):
    if not value:
        return ''
    return value.strftime('%d/%m/%Y')


def _build_contract_termination_export_csv_bytes(task=None, request=None):
    last_reading_qs = (
        Reading.objects.filter(contract_id=OuterRef('contract_id'))
        .order_by('-reading_date', '-id')
    )

    last_invoice_qs = (
        Invoice.objects.filter(
            contract_id=OuterRef('contract_id'),
            is_active=True,
            is_suppressed=False,
            type_final='F',
        )
        .exclude(status_id=1)
        .order_by('-issue_date', '-id')
    )

    queryset = (
        ContractTerminationRequest.objects.filter(is_active=True)
        .exclude(status_id__in=[2, 4])
        .select_related('contract', 'status')
        .annotate(
            last_reading_id=Subquery(last_reading_qs.values('id')[:1]),
            last_reading_date=Subquery(last_reading_qs.values('reading_date')[:1]),
            last_reading_origin=Subquery(last_reading_qs.values('origin')[:1]),
            last_invoice_id=Subquery(last_invoice_qs.values('id')[:1]),
            last_invoice_token=Subquery(last_invoice_qs.values('serie_final')[:1]),
            last_invoice_date=Subquery(last_invoice_qs.values('issue_date')[:1]),
        )
        .order_by('created_at', 'id')
    )

    if request is not None:
        multi_ids = get_multi_ids(request.data)
        q = None
        if multi_ids['contract_ids']:
            q = Q(contract_id__in=multi_ids['contract_ids'])
        if multi_ids['person_ids']:
            person_q = (
                Q(contract__owner_id__in=multi_ids['person_ids'])
                | Q(contract__tenant_id__in=multi_ids['person_ids'])
                | Q(contract__holder_id__in=multi_ids['person_ids'])
            )
            q = person_q if q is None else q & person_q
        if q:
            queryset = queryset.filter(q).distinct()

    buffer = StringIO()
    buffer.write('\ufeff')
    writer = csv.writer(buffer, delimiter=';')
    writer.writerow(_headers())

    total = queryset.count()
    for counter, row in enumerate(queryset.iterator(chunk_size=1000), start=1):
        if task and counter % 50 == 0:
            task.update_state(
                state='PROGRESS',
                meta={
                    'current': counter,
                    'total': total,
                    'percent': round((counter / total) * 100, 2) if total else 0.0
                }
            )
        writer.writerow(
            [
                row.contract_id or '',
                row.contract.token if row.contract else '',
                row.id,
                (row.status.token if row.status else '') or '',
                _fmt_date(row.created_at.date() if row.created_at else None),
                row.last_reading_id or '',
                _fmt_date(row.last_reading_date),
                row.last_reading_origin or '',
                row.last_invoice_id or '',
                row.last_invoice_token or '',
                _fmt_date(row.last_invoice_date),
            ]
        )

    return buffer.getvalue().encode('utf-8')


def generate_contract_termination_export_report(request, black_fill=None, white_bold_font=None, task=None):
    from statistics.views.reports_views import save_report

    name = request.data.get('name', '') or 'Baixes de contracte: lectura i factura'
    type_id = request.data.get('type_id', None)

    body = _build_contract_termination_export_csv_bytes(task=task, request=request)
    filename = (
        f"contract_termination_last_reading_invoice_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )

    document_id = save_report(content=body, filename=filename, name=name, type_id=type_id)

    response = HttpResponse(body, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response, document_id, filename
