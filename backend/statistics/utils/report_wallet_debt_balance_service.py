"""Informe de deute i saldo per contracte a una data de tall.

Per a cada contracte calcula, tal com estava a la data de tall:
- Saldo positiu: suma dels moviments de guardiola (PiggyBankMovement) fins a la data.
- Deute: suma dels imports dels pagaments que a la data estaven en un estat pendent de
  cobrament. L'estat d'un pagament a la data es reconstrueix amb l'historial de
  PaymentMovement (l'estat actual del pagament no serveix per a dates passades).
"""
import datetime
import logging
from decimal import Decimal

import openpyxl
from django.db.models import Case, DecimalField, F, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce, TruncDate
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.response import Response

from billing.models import Invoice, Payment, PaymentMovement
from contract.models import Contract, PiggyBankMovement
from coredata.models import ConfigProject
from statistics.utils.report_filters import contract_multi_filter_q, get_multi_ids
from statistics.utils.report_progress import report_progress
from statistics.views.reports_views import add_row, adjust_column_widths, save_report

logger = logging.getLogger(__name__)

# Estats de pagament que compten com a deute a la data de tall (tokens a ConfigProject).
DEBT_STATUS_CONFIG_TOKENS = (
    'payment_status_pending_token',
    'payment_status_sent_token',
    'payment_status_expired_token',
    'payment_status_returned_token',
    'payment_status_endowment_token',
)

ZERO = Decimal('0.00')


def parse_cutoff_date(value):
    """Accepta 'AAAA-MM-DD' o un ISO amb hora (només es fa servir la part de data)."""
    if not value:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def get_debt_status_tokens():
    return list(
        ConfigProject.objects.filter(token__in=DEBT_STATUS_CONFIG_TOKENS)
        .exclude(value__isnull=True)
        .exclude(value='')
        .values_list('value', flat=True)
    )


def _payments_status_at(cutoff_date):
    """Pagaments existents a la data de tall, anotats amb `status_at` i `contract_ref`.

    - Si hi ha moviments fins a la data, l'estat és el `current_status` de l'últim.
    - Si només n'hi ha de posteriors, l'estat és el `previous_status` del primer.
    - Si no en té cap, l'estat és l'actual del pagament.
    - Si l'estat actual no coincideix amb el de l'últim moviment, hi ha hagut un canvi
      sense moviment (p. ex. el pagament passa a abonat en rectificar la factura). Aquest
      canvi es data amb l'emissió de la factura rectificativa o, si no n'hi ha,
      amb `updated_at`, i s'aplica si és anterior o igual a la data de tall.
    Un pagament existeix a la data si té moviments fins llavors o si la seva data d'origen
    (emissió de la factura, inici del compromís o creació) és anterior o igual.
    """
    movements = PaymentMovement.objects.filter(payment=OuterRef('pk'), is_active=True)
    last_before = (
        movements.filter(movement_date__lte=cutoff_date)
        .order_by('-movement_date', '-timestamp', '-id')
    )
    first_after = (
        movements.filter(movement_date__gt=cutoff_date)
        .order_by('movement_date', 'timestamp', 'id')
    )
    last_overall = movements.order_by('-movement_date', '-timestamp', '-id')
    rectifying_issue_date = Invoice.objects.filter(
        token=OuterRef('invoice__return_token'),
    ).exclude(token__isnull=True).exclude(token='').values('issue_date')[:1]
    contract_from_request = Contract.objects.filter(
        contract_request_id=OuterRef('invoice__contract_request_id'),
    ).order_by('id').values('id')[:1]

    return (
        Payment.objects.filter(is_active=True)
        .annotate(
            status_before=Subquery(last_before.values('current_status__token')[:1]),
            has_after=Subquery(first_after.values('id')[:1]),
            status_prev_after=Subquery(first_after.values('previous_status__token')[:1]),
            status_last=Subquery(last_overall.values('current_status__token')[:1]),
            origin_date=Coalesce(
                'invoice__issue_date',
                'commitment_deposit__start_date',
                TruncDate('created_at'),
            ),
        )
        .filter(Q(status_before__isnull=False) | Q(origin_date__lte=cutoff_date))
        .annotate(
            untracked_change_date=Coalesce(Subquery(rectifying_issue_date), TruncDate('updated_at')),
        )
        .annotate(
            status_at=Case(
                When(
                    Q(status_last__isnull=False)
                    & ~Q(status_last=F('status__token'))
                    & Q(untracked_change_date__lte=cutoff_date),
                    then=F('status__token'),
                ),
                When(status_before__isnull=False, then=F('status_before')),
                When(has_after__isnull=False, then=F('status_prev_after')),
                default=F('status__token'),
            ),
            contract_ref=Coalesce(
                'invoice__contract_id',
                'invoice__contract_termination__contract_id',
                Subquery(contract_from_request),
                'commitment_deposit__contract_id',
                'contract_id',
            ),
        )
    )


def get_contract_debts_at(cutoff_date, debt_status_tokens):
    """{contract_id: deute} amb els pagaments en estat de deute a la data."""
    rows = (
        _payments_status_at(cutoff_date)
        .filter(status_at__in=debt_status_tokens, contract_ref__isnull=False)
        .values('contract_ref')
        .annotate(total=Sum('amount'))
    )
    return {row['contract_ref']: row['total'] or ZERO for row in rows}


def get_contract_balances_at(cutoff_date):
    """{contract_id: saldo} amb els moviments de guardiola fins a la data."""
    signed_amount = Case(
        When(is_positive=True, then=F('amount')),
        default=-F('amount'),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
    rows = (
        PiggyBankMovement.objects.filter(is_active=True, movement_date__lte=cutoff_date)
        .values('piggy_bank_id')
        .annotate(total=Coalesce(Sum(signed_amount), Value(ZERO)))
    )
    balance_by_piggy_bank = {row['piggy_bank_id']: row['total'] for row in rows}
    if not balance_by_piggy_bank:
        return {}

    balances = {}
    contracts = Contract.objects.filter(piggy_bank_id__in=balance_by_piggy_bank.keys()).values_list('id', 'piggy_bank_id')
    for contract_id, piggy_bank_id in contracts:
        balances[contract_id] = balance_by_piggy_bank[piggy_bank_id]
    return balances


def generate_wallet_debt_balance_at_date_report(request, black_fill=None, white_bold_font=None, task=None):
    try:
        data = request.data
        name = data.get('name', '') or 'deute_saldo'
        type_id = data.get('type_id', None)
        exploitation_id = data.get('exploitation_id', None)

        cutoff_date = parse_cutoff_date(data.get('cutoff_date'))
        if cutoff_date is None:
            return Response({"error": _("Cal indicar una data.")}, status=status.HTTP_400_BAD_REQUEST), None, None

        debts = get_contract_debts_at(cutoff_date, get_debt_status_tokens())
        balances = get_contract_balances_at(cutoff_date)

        contract_ids = {cid for cid, value in debts.items() if value} | {cid for cid, value in balances.items() if value}

        contracts = Contract.objects.filter(id__in=contract_ids).select_related('holder')
        if exploitation_id and exploitation_id != 'all':
            contracts = contracts.filter(supply_point_default__connection__exploitation_id=exploitation_id)
        multi_ids = get_multi_ids(data)
        contract_multi_q = contract_multi_filter_q(person_ids=multi_ids['person_ids'], contract_ids=multi_ids['contract_ids'])
        if contract_multi_q:
            contracts = contracts.filter(contract_multi_q).distinct()
        contracts = contracts.order_by('token')

        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = cutoff_date.strftime('%d-%m-%Y')

        row = 0
        titles = [_("Contracte"), _("Titular"), _("NIF"), _("Saldo positiu"), _("Deute")]
        row = add_row(sheet, row, titles, fill=black_fill, font=white_bold_font)

        total = contracts.count()
        total_balance = ZERO
        total_debt = ZERO
        for index, contract in enumerate(contracts.iterator(chunk_size=2000), start=1):
            report_progress(task, index, total, every=500)
            balance = balances.get(contract.id, ZERO)
            debt = debts.get(contract.id, ZERO)
            total_balance += balance
            total_debt += debt
            holder = contract.holder
            row = add_row(sheet, row, [
                contract.token or "",
                str(holder).strip() if holder else "",
                (holder.token or "") if holder else "",
                balance,
                debt,
            ])

        row = add_row(sheet, row, [_("Total"), "", "", total_balance, total_debt], fill=black_fill, font=white_bold_font)

        for line in sheet.iter_rows(min_row=2, min_col=4, max_col=5):
            for cell in line:
                cell.number_format = '#,##0.00'
        adjust_column_widths(sheet)

        filename = f"{name}_{cutoff_date.strftime('%Y%m%d')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        document_id = save_report(content=wb, filename=filename, name=name, type_id=type_id)
        return None, document_id, filename
    except Exception:
        logger.exception("Error inesperat generant l'informe de deute i saldo a data")
        return Response({"error": "Ha ocorregut un error inesperat."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None
