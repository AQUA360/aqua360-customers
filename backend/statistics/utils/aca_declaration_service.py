"""Selecció de factures de la Declaració ACA (A1) per dates, compartida amb el FACTDETA.

Els mesos ja presentats (AcaDeclaration) queden congelats: en surten exactament les línies de cànon que es
van declarar, encara que després la factura s'hagi anul·lat, desactivat o canviat. Les factures d'un mes
presentat que no s'hi van declarar (creades després, amb data d'emissió anterior) passen al primer mes
de la mateixa explotació que encara no s'ha presentat.
"""
import calendar
import datetime
from decimal import Decimal
from types import SimpleNamespace

from django.db.models import Q

from billing.models import Invoice, InvoiceLineItem
from coredata.models import ConfigProject
from statistics.models import AcaDeclaration
from statistics.utils.report_filters import apply_exclude_billing_ids, apply_serie_final_range, apply_serie_ids
from statistics.views.reports_views import filter_pending_invoices


def current_aca_invoices(start_date, end_date):
    """Factures emeses dins el període que entren a la Declaració ACA segons el seu estat actual."""
    invoice_type = ConfigProject.objects.get(token="invoice_type_invoice_token").value
    status_cancelled_token = ConfigProject.objects.get(token="invoice_status_cancelled_token").value
    # Excloure les anul·lades NOMÉS si no tenen una refactura/abonament lligat (return_token).
    # Les anul·lades amb return_token es mantenen (mateix criteri que el detall de facturació).
    return Invoice.objects.filter(
        issue_date__range=(start_date, end_date),
        type_final=invoice_type,
        payments__is_active=True,
        exploitation__isnull=False,
    ).exclude(
        Q(status__token__in=[status_cancelled_token])
        & (Q(return_token__isnull=True) | Q(return_token__exact=""))
    ).distinct()


def month_range(year, month):
    return datetime.date(year, month, 1), datetime.date(year, month, calendar.monthrange(year, month)[1])


def _next_month(year, month):
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _first_open_month(exploitation_id, year, month, frozen):
    """Primer mes posterior al donat que l'explotació encara no ha presentat."""
    year, month = _next_month(year, month)
    while (exploitation_id, year, month) in frozen:
        year, month = _next_month(year, month)
    return year, month


def _frozen_months_q(keys):
    q = Q()
    for exploitation_id, year, month in keys:
        q |= Q(exploitation_id=exploitation_id, issue_date__range=month_range(year, month))
    return q


def declared_line_ids(declarations):
    return AcaDeclaration.line_items.through.objects.filter(
        acadeclaration__in=declarations,
    ).values('invoicelineitem_id')


def aca_declaration_selection(start_date, end_date, request):
    """Factures i línies de cànon que declara l'A1 per dates entre start_date i end_date (dates).

    Retorna `invoices` (queryset de factures) i `line_items_q` (Q per a InvoiceLineItem): sense mesos
    presentats és el criteri actual amb les línies actives."""
    current = filter_pending_invoices(current_aca_invoices(start_date, end_date), request)
    declarations = list(AcaDeclaration.objects.only('id', 'exploitation_id', 'year', 'month'))
    if not declarations:
        return SimpleNamespace(invoices=current, line_items_q=Q(is_active=True))

    # Els identificadors es calculen aquí un sol cop: com a subconsultes (NOT IN de totes les factures
    # declarades) Postgres les avalua fila per fila i l'A1 d'un any no acaba
    frozen = {(d.exploitation_id, d.year, d.month) for d in declarations}
    start_key, end_key = (start_date.year, start_date.month), (end_date.year, end_date.month)
    declared_invoice_ids = set(InvoiceLineItem.objects.filter(
        id__in=declared_line_ids(declarations),
    ).values_list('invoice_id', flat=True))

    # Mesos presentats dins el període: les línies declarades. Si el període només en cobreix una
    # part, les de les factures emeses dins el període.
    frozen_lines_q = Q(pk__in=[])
    for declaration in declarations:
        if not start_key <= (declaration.year, declaration.month) <= end_key:
            continue
        first_day, last_day = month_range(declaration.year, declaration.month)
        lines_q = Q(id__in=declared_line_ids([declaration.id]))
        if first_day < start_date or last_day > end_date:
            lines_q &= Q(invoice__issue_date__range=(start_date, end_date))
        frozen_lines_q |= lines_q
    frozen_invoice_ids = set(InvoiceLineItem.objects.filter(frozen_lines_q).values_list('invoice_id', flat=True))

    # Mesos oberts: el criteri actual, sense les factures ja declarades en algun mes
    open_ids = {
        invoice_id for invoice_id, exploitation_id, issue_date in current.values_list('id', 'exploitation_id', 'issue_date')
        if invoice_id not in declared_invoice_ids and (exploitation_id, issue_date.year, issue_date.month) not in frozen
    }

    # Factures d'un mes presentat que no s'hi van declarar: al primer mes obert de l'explotació
    frozen_before_end = [key for key in frozen if key[1:] <= end_key]
    if frozen_before_end:
        first_frozen = min(month_range(year, month)[0] for _e, year, month in frozen_before_end)
        candidates = filter_pending_invoices(current_aca_invoices(first_frozen, end_date), request).filter(
            _frozen_months_q(frozen_before_end),
        ).values_list('id', 'exploitation_id', 'issue_date')
        open_ids |= {
            invoice_id for invoice_id, exploitation_id, issue_date in candidates
            if invoice_id not in declared_invoice_ids
            and start_key <= _first_open_month(exploitation_id, issue_date.year, issue_date.month, frozen) <= end_key
        }

    # Els filtres de lot i de sèrie de l'informe també valen per als mesos presentats (l'estat, no)
    invoices = Invoice.objects.filter(id__in=sorted(open_ids | frozen_invoice_ids))
    invoices = apply_exclude_billing_ids(invoices, request.data, field='billing_id')
    invoices = apply_serie_final_range(apply_serie_ids(invoices, request.data, field='serie_final'), request.data)
    line_items_q = frozen_lines_q | Q(is_active=True, invoice_id__in=sorted(open_ids))
    return SimpleNamespace(invoices=invoices, line_items_q=line_items_q)


def build_aca_declaration(exploitation, year, month, presented_at, listed_numbers=(), include=(), exclude=()):
    """Línies de cànon que es van declarar en un mes ja presentat, reconstruïdes amb l'estat actual:
    les factures del mes que entren a l'A1 creades fins a `presented_at`, més les que el full de factures
    de l'informe presentat llista (encara que després s'hagin anul·lat o desactivat) i les indicades a mà.
    D'una factura sense cap línia de cànon activa s'agafen les desactivades (es van declarar així)."""
    from statistics.utils.report_billing_service import _aca_product_token_q

    aca_product_token = ConfigProject.objects.get(token="token_product_aca").value
    pending_token = ConfigProject.objects.get(token="invoice_status_pending_token").value
    first_day, last_day = month_range(year, month)
    other_declarations = AcaDeclaration.objects.exclude(exploitation=exploitation, year=year, month=month)
    declared_elsewhere = set(InvoiceLineItem.objects.filter(
        id__in=declared_line_ids(other_declarations),
    ).values_list('invoice_id', flat=True))

    invoice_ids = set(current_aca_invoices(first_day, last_day).filter(
        exploitation=exploitation, created_at__lte=presented_at, is_excluded=False,
    ).exclude(status__token=pending_token).values_list('id', flat=True))

    listed = dict(Invoice.objects.filter(
        exploitation=exploitation, serie_final__in=list(listed_numbers),
    ).exclude(status__token=pending_token).values_list('serie_final', 'id'))
    unresolved = sorted(set(listed_numbers) - set(listed))
    forced = dict(Invoice.objects.filter(
        exploitation=exploitation, serie_final__in=list(include),
    ).values_list('serie_final', 'id'))
    unresolved += sorted(set(include) - set(forced))
    excluded = set(Invoice.objects.filter(
        exploitation=exploitation, serie_final__in=list(exclude),
    ).values_list('id', flat=True))
    invoice_ids = (invoice_ids | set(listed.values()) | set(forced.values())) - excluded - declared_elsewhere

    lines_by_invoice = {}
    for line in InvoiceLineItem.objects.filter(
        _aca_product_token_q('product__token', aca_product_token), invoice_id__in=invoice_ids,
    ).select_related('line_item_type__article'):
        lines_by_invoice.setdefault(line.invoice_id, []).append(line)

    line_ids, fixed, variable, inactive_line_invoices = [], Decimal(0), Decimal(0), []
    for invoice_id, lines in lines_by_invoice.items():
        active = [line for line in lines if line.is_active]
        if not active:
            inactive_line_invoices.append(invoice_id)
        for line in active or lines:
            line_ids.append(line.id)
            article = line.line_item_type.article if line.line_item_type else None
            if article and article.token == 'part_fixa':
                fixed += Decimal(str(line.price or 0))
            else:
                variable += Decimal(str(line.price or 0))

    return SimpleNamespace(
        line_ids=line_ids,
        invoice_ids=set(lines_by_invoice),
        fixed_amount=fixed.quantize(Decimal('0.01')),
        variable_amount=variable.quantize(Decimal('0.01')),
        unresolved=unresolved,
        inactive_line_invoices=inactive_line_invoices,
    )
