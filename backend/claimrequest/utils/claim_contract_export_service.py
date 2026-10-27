"""
Exportació a Excel dels llistats de contractes d'una gestió de reclamació
(tant en crear-la com en qualsevol dels seus passos).
"""
from decimal import Decimal

from django.db.models import Count, Prefetch
from django.utils import timezone
from django.utils.translation import gettext as _

from billing.models import Invoice, Payment
from billing.utils.joined_payment_service import CONTRACT_DEBT_EXCLUDED_STATUS_TOKENS
from contract.models import Contract
from contract.utils.contract_csv_export import _person_label, _supply_point_address
from contract.utils.contract_list_queryset import contract_debt_amounts_by_contract_id
from coredata.models import ConfigProject
from service.models import SupplyCut
from service.utils.supply_cut_service import closed_status_tokens


def unpaid_invoices_count_by_contract_id(contract_ids):
    """
    Factures amb algun pagament que compta com a deute (mateixa definició que
    vw_contract_debt), sense comptar les factures de recàrrec per devolució
    (línia amb la PriceRate de `invoice_return_price_rate_token`).
    """
    payments = Payment.objects.filter(
        invoice__contract_id__in=contract_ids,
        status__isnull=False,
        amount__gt=0,
    ).exclude(status__token__in=CONTRACT_DEBT_EXCLUDED_STATUS_TOKENS)

    return_fee_price_rate_token = ConfigProject.objects.filter(
        token='invoice_return_price_rate_token'
    ).values_list('value', flat=True).first()
    if return_fee_price_rate_token:
        # Subconsulta d'ids: filtrar per `line_items__...` aquí duplicaria files al Count.
        payments = payments.exclude(invoice_id__in=Invoice.objects.filter(
            contract_id__in=contract_ids,
            line_items__price_rate__token=return_fee_price_rate_token,
        ).values('id'))

    rows = payments.values('invoice__contract_id').annotate(total=Count('invoice_id', distinct=True))
    return {row['invoice__contract_id']: row['total'] for row in rows}


def _supply_cut_date(contract):
    """Data del tall actiu o previst del punt de subministrament per defecte (real si ja ha començat)."""
    supply_point = contract.supply_point_default
    if not supply_point:
        return ''
    for supply_cut in supply_point.open_supply_cuts:
        cut_date = supply_cut.exec_start or supply_cut.date_start
        if cut_date:
            return timezone.localtime(cut_date).strftime('%d/%m/%Y')
    return ''


def claim_contracts_export_queryset():
    # Talls oberts: actius o previstos (no tancats ni cancel·lats).
    open_supply_cuts = SupplyCut.objects.filter(is_active=True).exclude(
        status__token__in=closed_status_tokens()
    ).order_by('-id')
    return Contract.objects.select_related(
        'holder',
        'status',
        'supply_point_default__status',
        'supply_point_default__meter',
        'supply_point_default__address__street__type',
        'supply_point_default__address__street_number__number_type',
        'supply_point_default__address__city',
        'supply_point_default__address__country',
    ).prefetch_related(
        Prefetch('supply_point_default__supply_cuts', queryset=open_supply_cuts, to_attr='open_supply_cuts'),
    )


def claim_contracts_export_columns(contract_ids):
    debt_by_contract = contract_debt_amounts_by_contract_id(contract_ids)
    unpaid_by_contract = unpaid_invoices_count_by_contract_id(contract_ids)

    def meter_code(contract):
        supply_point = contract.supply_point_default
        return supply_point.meter.code or '' if supply_point and supply_point.meter else ''

    def supply_point_status(contract):
        supply_point = contract.supply_point_default
        return supply_point.status.name or '' if supply_point and supply_point.status else ''

    return [
        ('token', _('Contracte'), lambda c: c.token or ''),
        ('holder', _('Titular'), lambda c: _person_label(c.holder)),
        ('supply_address', _('Adreça subministrament'), lambda c: _supply_point_address(c.supply_point_default)),
        ('unpaid_invoices', _('Factures impagades'), lambda c: unpaid_by_contract.get(c.id, 0)),
        ('debt', _('Deute total'), lambda c: debt_by_contract.get(c.id, Decimal('0'))),
        ('meter', _('Comptador'), meter_code),
        ('status', _('Estat contracte'), lambda c: c.status.name if c.status else ''),
        ('supply_point_status', _('Estat punt de subministrament'), supply_point_status),
        ('supply_cut_date', _('Data de tall'), _supply_cut_date),
    ]
