"""Període facturat de les factures i relacions entre factures per a la llista del contracte.

L'any d'una factura és el del període facturat (`billing_period_year`) i, si no en té,
el de la data d'emissió. Les factures sense cap de les dues dates van a part (`NO_PERIOD`).
"""
from django.db.models import Count, Q
from django.db.models.functions import Coalesce, ExtractYear

from billing.models import Invoice

NO_PERIOD = 'none'


def annotate_period_year(queryset):
    return queryset.annotate(
        period_year_value=Coalesce('billing_period_year', ExtractYear('issue_date'))
    )


def filter_period_year(queryset, value):
    """Filtra per any del període; `none` torna les factures sense període ni data d'emissió."""
    if value == NO_PERIOD:
        return queryset.filter(billing_period_year__isnull=True, issue_date__isnull=True)
    try:
        year = int(value)
    except (TypeError, ValueError):
        return queryset.none()
    return queryset.filter(
        Q(billing_period_year=year) | Q(billing_period_year__isnull=True, issue_date__year=year)
    )


def period_year_counts(queryset):
    """Anys amb factures, del més recent al més antic, i al final les que no tenen període."""
    rows = (
        annotate_period_year(queryset.order_by())
        .values('period_year_value')
        .annotate(count=Count('id'))
    )
    years = sorted(
        ({'year': row['period_year_value'], 'count': row['count']}
         for row in rows if row['period_year_value'] is not None),
        key=lambda row: row['year'], reverse=True,
    )
    without_period = sum(row['count'] for row in rows if row['period_year_value'] is None)
    if without_period:
        years.append({'year': NO_PERIOD, 'count': without_period})
    return years


def _link(invoice):
    return {'id': invoice.id, 'token': invoice.token, 'serie_final': invoice.serie_final}


def invoice_relations_map(invoices, invoice_type_token):
    """Abonaments i refacturacions de cada factura, amb una consulta per tipus de relació.

    - `rectifying_invoice`: abonament que anul·la la factura (`return_token` de la factura).
    - `rectified_invoice`: factura que abona aquest abonament.
    - `refactored_invoice`: factura original que aquesta refà (`refactored_token`).
    - `refactor_invoice`: factura nova que refà aquesta.
    """
    relations = {invoice.id: {} for invoice in invoices}
    tokens = {invoice.token for invoice in invoices if invoice.token}
    return_tokens = {invoice.return_token for invoice in invoices if invoice.return_token}
    refactored_tokens = {invoice.refactored_token for invoice in invoices if invoice.refactored_token}
    linked = Invoice.objects.filter(type__token=invoice_type_token).only(
        'id', 'token', 'serie_final', 'return_token', 'refactored_token', 'created_at'
    ).order_by('-created_at')

    by_token = {}
    if return_tokens or refactored_tokens:
        for invoice in linked.filter(token__in=return_tokens | refactored_tokens):
            by_token.setdefault(invoice.token, invoice)

    rectified_by_token = {}
    refactor_by_token = {}
    if tokens:
        for invoice in linked.filter(Q(return_token__in=tokens) | Q(refactored_token__in=tokens)):
            if invoice.return_token in tokens:
                rectified_by_token.setdefault(invoice.return_token, invoice)
            if invoice.refactored_token in tokens:
                refactor_by_token.setdefault(invoice.refactored_token, invoice)

    for invoice in invoices:
        relation = relations[invoice.id]
        if invoice.return_token and invoice.return_token in by_token:
            relation['rectifying_invoice'] = _link(by_token[invoice.return_token])
        if invoice.refactored_token and invoice.refactored_token in by_token:
            relation['refactored_invoice'] = _link(by_token[invoice.refactored_token])
        if invoice.token in rectified_by_token:
            relation['rectified_invoice'] = _link(rectified_by_token[invoice.token])
        if invoice.token in refactor_by_token:
            relation['refactor_invoice'] = _link(refactor_by_token[invoice.token])
    return relations
