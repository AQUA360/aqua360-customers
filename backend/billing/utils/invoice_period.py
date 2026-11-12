"""Període facturat de les factures i relacions entre factures per a la llista del contracte.

El període d'una factura de consum és el cicle del facturador (`period_type` i
`initial_month`): una factura trimestral emesa a l'octubre amb lectures de juny a
setembre és de Juliol-Setembre. Les factures puntuals (altes, despeses...) i les que no
tenen facturador van al mes del període desat a la factura (o de la data d'emissió).
L'any de la pestanya és el del darrer mes del cicle. Les factures sense cap data van a
part (`NO_PERIOD`).
"""
from collections import defaultdict
from types import SimpleNamespace

from django.db.models import Q

from billing.models import Invoice
from billing.templatetags.billing_filters import (
    PERIOD_TYPE_MONTHS, _cycle_bounds_from_biller, _invoice_period_anchor, get_config,
)

NO_PERIOD = 'none'


def _month_index(year, month):
    return year * 12 + (month - 1)


def _from_index(index):
    year, month = divmod(index, 12)
    return year, month + 1


def _single_month(year, month):
    return {'start_year': year, 'start_month': month, 'end_year': year, 'end_month': month}


def _contract_billers(contract_ids):
    """Facturador de la ruta de cada contracte, per a les factures fetes fora d'una facturació."""
    from contract.models import Contract
    from service.utils.route_scope import effective_route

    billers = {}
    for contract in Contract.objects.filter(id__in=contract_ids).select_related('supply_point_default'):
        try:
            billers[contract.id] = effective_route(contract.supply_point_default).biller
        except Exception:
            billers[contract.id] = None
    return billers


def _billed_month(row):
    """Mes desat a la factura (període o, si no n'hi ha, data d'emissió)."""
    if row['billing_period_year'] and row['billing_period_month'] and 1 <= row['billing_period_month'] <= 12:
        return row['billing_period_year'], row['billing_period_month']
    if row['issue_date']:
        return row['issue_date'].year, row['issue_date'].month
    return None


def _cycle(row, readings, biller, consumption_origin):
    """Cicle facturat d'una factura (diccionari amb inici i final) o None si no té cap data.

    `readings` buit vol dir que no n'hi ha o que no són fiables per situar-la.
    """
    billed = _billed_month(row)

    interval = PERIOD_TYPE_MONTHS.get(getattr(biller, 'period_type', None))
    if row['origin__token'] != consumption_origin or not interval:
        return _single_month(*billed) if billed else None

    # La factura s'emet el mes següent al final del període.
    anchor = _from_index(_month_index(*billed) - 1) if billed else None
    if readings:
        invoice = SimpleNamespace(readings=SimpleNamespace(all=lambda: readings))
        anchor = _invoice_period_anchor(invoice, interval) or anchor
    if anchor is None:
        return None
    bounds = _cycle_bounds_from_biller(anchor[0], anchor[1], biller)
    if not bounds:
        return _single_month(*anchor)
    start_month, start_year, end_month, end_year = bounds
    return {'start_year': start_year, 'start_month': start_month, 'end_year': end_year, 'end_month': end_month}


def invoice_billing_cycles(queryset):
    """{id de factura: cicle facturat} amb unes poques consultes (pensat per a un contracte)."""
    rows = list(queryset.order_by().values(
        'id', 'token', 'return_token', 'contract_id', 'billing_period_year', 'billing_period_month',
        'issue_date', 'origin__token', 'billing__biller__period_type', 'billing__biller__initial_month',
    ))
    if not rows:
        return {}
    ids = [row['id'] for row in rows]
    # Abonament -> factura que anul·la (la factura anul·lada desa el token de l'abonament)
    rectified_by_credit = {}
    id_by_token = {row['token']: row['id'] for row in rows if row['token']}
    for row in rows:
        if row['return_token'] in id_by_token:
            rectified_by_credit.setdefault(id_by_token[row['return_token']], row['id'])

    links = list(Invoice.readings.through.objects.filter(invoice_id__in=ids).values(
        'invoice_id', 'reading_id', 'reading__reading_date', 'reading__previous_reading_id',
        'reading__previous_reading__reading_date',
    ))
    # Una lectura enllaçada a factures de períodes desats diferents (p. ex. un lot que refà
    # períodes antics) no situa cap d'elles: mana el període desat. Els abonaments i les
    # factures refetes copien el període de l'original, així que hi continuen comptant.
    billed_by_id = {row['id']: _billed_month(row) for row in rows}
    periods_by_reading = defaultdict(set)
    for item in links:
        if item['invoice_id'] not in rectified_by_credit:
            periods_by_reading[item['reading_id']].add(billed_by_id[item['invoice_id']])
    readings = defaultdict(list)
    for item in links:
        if len(periods_by_reading[item['reading_id']]) > 1:
            continue
        previous_date = item['reading__previous_reading__reading_date']
        readings[item['invoice_id']].append(SimpleNamespace(
            reading_date=item['reading__reading_date'],
            previous_reading_id=item['reading__previous_reading_id'],
            previous_reading=SimpleNamespace(reading_date=previous_date) if previous_date else None,
        ))

    consumption_origin = get_config('origin_reading_token', 'aigua')
    route_billers = _contract_billers({
        row['contract_id'] for row in rows
        if row['contract_id'] and not row['billing__biller__period_type']
        and row['origin__token'] == consumption_origin
    })

    cycles = {}
    for row in rows:
        if row['billing__biller__period_type']:
            biller = SimpleNamespace(
                period_type=row['billing__biller__period_type'],
                initial_month=row['billing__biller__initial_month'],
            )
        else:
            biller = route_billers.get(row['contract_id'])
        cycles[row['id']] = _cycle(row, readings.get(row['id'], []), biller, consumption_origin)
    # L'abonament és del mateix període que la factura que anul·la, encara que s'emeti després
    for credit_id, rectified_id in rectified_by_credit.items():
        cycles[credit_id] = cycles[rectified_id]
    return cycles


# Estat de cobrament per al resum de cada període de la pestanya del contracte.
PAID = 'paid'
PENDING = 'pending'
EXPIRED = 'expired'
SETTLED = 'settled'  # anul·lades, abonades i abonaments: no compten en el resum
PAYMENT_STATE_TOKENS = {
    'invoice_status_paid_token': PAID,
    'invoice_status_expired_token': EXPIRED,
    'invoice_status_irrecoverable_token': EXPIRED,
    'invoice_status_part_irrecoverable_token': EXPIRED,
    'invoice_status_endowment_token': EXPIRED,
    'invoice_status_cancelled_token': SETTLED,
    'invoice_status_dropped_token': SETTLED,
    'invoice_status_payoff_token': SETTLED,
}


def invoice_payment_states(invoices, today):
    """{id: estat de cobrament}. Una factura pendent amb el venciment passat compta com a vençuda."""
    from coredata.models import ConfigProject

    state_by_status = {
        value: PAYMENT_STATE_TOKENS[token]
        for token, value in ConfigProject.objects.filter(
            token__in=PAYMENT_STATE_TOKENS).values_list('token', 'value')
        if value
    }
    states = {}
    for invoice in invoices:
        status_token = invoice.status.token if invoice.status_id and invoice.status else None
        state = state_by_status.get(status_token)
        if state is None and status_token is not None:
            state = EXPIRED if invoice.due_date and invoice.due_date < today else PENDING
        states[invoice.id] = state
    return states



def invoice_payment_summaries(invoices):
    """{id: estat del cobrament i retorns} per a la columna «Estat de pagament» de la llista del contracte.

    - `payment_status`: estat del darrer cobrament actiu que no està anul·lat (o del darrer, si
      tots ho estan), amb el color de la taula mestra.
    - `returned_at` i `returned_count`: data del darrer retorn bancari i nombre de retorns, encara
      que després s'hagi tornat a cobrar. Compten els moviments de retorn actius.

    Tres consultes (configuració, cobraments i retorns), sigui quin sigui el nombre de factures.
    """
    from billing.models import Payment, PaymentMovement
    from coredata.models import ConfigProject

    ids = [invoice.id for invoice in invoices]
    summaries = {id: {'payment_status': None, 'returned_at': None, 'returned_count': 0} for id in ids}
    if not ids:
        return summaries
    config = dict(ConfigProject.objects.filter(
        token__in=['payment_status_cancelled_token', 'payment_status_returned_token'],
    ).values_list('token', 'value'))
    cancelled_token = config.get('payment_status_cancelled_token')
    returned_token = config.get('payment_status_returned_token')

    payments = defaultdict(list)
    for payment in (Payment.objects.filter(invoice_id__in=ids, is_active=True)
                    .select_related('status').order_by('created_at', 'id')):
        payments[payment.invoice_id].append(payment)
    for invoice_id, invoice_payments in payments.items():
        live = [payment for payment in invoice_payments
                if not (payment.status and payment.status.token == cancelled_token)]
        status = (live or invoice_payments)[-1].status
        if status:
            summaries[invoice_id]['payment_status'] = {
                'name': status.name, 'color': status.color, 'token': status.token,
            }

    if returned_token:
        for invoice_id, movement_date, timestamp in PaymentMovement.objects.filter(
            payment__invoice_id__in=ids, payment__is_active=True,
            is_active=True, current_status__token=returned_token,
        ).values_list('payment__invoice_id', 'movement_date', 'timestamp'):
            summary = summaries[invoice_id]
            returned_at = movement_date or (timestamp.date() if timestamp else None)
            summary['returned_count'] += 1
            if returned_at and (summary['returned_at'] is None or returned_at > summary['returned_at']):
                summary['returned_at'] = returned_at
    return summaries


def cycle_year(cycle):
    return cycle['end_year'] if cycle else NO_PERIOD


def filter_period_year(queryset, value):
    """Factures d'un any de cicle; `none` torna les que no tenen cap data."""
    if value != NO_PERIOD:
        try:
            value = int(value)
        except (TypeError, ValueError):
            return queryset.none()
    cycles = invoice_billing_cycles(queryset)
    return queryset.filter(id__in=[id for id, cycle in cycles.items() if cycle_year(cycle) == value])


def period_year_counts(queryset):
    """Anys amb factures, del més recent al més antic, i al final les que no tenen període."""
    counts = defaultdict(int)
    for cycle in invoice_billing_cycles(queryset).values():
        counts[cycle_year(cycle)] += 1
    without_period = counts.pop(NO_PERIOD, 0)
    years = [{'year': year, 'count': counts[year]} for year in sorted(counts, reverse=True)]
    if without_period:
        years.append({'year': NO_PERIOD, 'count': without_period})
    return years


OWNER_FIELDS = ('contract_id', 'contract_request_id', 'connection_request_id')


def _link(invoice):
    return {'id': invoice.id, 'token': invoice.token, 'serie_final': invoice.serie_final}


def _same_owner(invoice, other):
    """El token no és únic: només s'enllacen factures del mateix contracte o sol·licitud."""
    return any(
        getattr(invoice, field) is not None and getattr(invoice, field) == getattr(other, field)
        for field in OWNER_FIELDS
    )


def _match(invoice, candidates):
    return next((other for other in candidates if _same_owner(invoice, other)), None)


def invoice_relations_map(invoices, invoice_type_token):
    """Abonaments i refacturacions de cada factura, amb una consulta per tipus de relació.
    Només s'enllacen factures actives del mateix contracte o sol·licitud.

    - `rectifying_invoice`: abonament que anul·la la factura (`return_token` de la factura).
    - `rectified_invoice`: factura que abona aquest abonament.
    - `refactored_invoice`: factura original que aquesta refà (`refactored_token`).
    - `refactor_invoice`: factura nova que refà aquesta.
    """
    relations = {invoice.id: {} for invoice in invoices}
    tokens = {invoice.token for invoice in invoices if invoice.token}
    return_tokens = {invoice.return_token for invoice in invoices if invoice.return_token}
    refactored_tokens = {invoice.refactored_token for invoice in invoices if invoice.refactored_token}
    linked = Invoice.objects.filter(type__token=invoice_type_token, is_active=True).only(
        'id', 'token', 'serie_final', 'return_token', 'refactored_token', 'created_at', *OWNER_FIELDS
    ).order_by('-created_at')

    by_token = defaultdict(list)
    if return_tokens or refactored_tokens:
        for invoice in linked.filter(token__in=return_tokens | refactored_tokens):
            by_token[invoice.token].append(invoice)

    rectified_by_token = defaultdict(list)
    refactor_by_token = defaultdict(list)
    if tokens:
        for invoice in linked.filter(Q(return_token__in=tokens) | Q(refactored_token__in=tokens)):
            if invoice.return_token in tokens:
                rectified_by_token[invoice.return_token].append(invoice)
            if invoice.refactored_token in tokens:
                refactor_by_token[invoice.refactored_token].append(invoice)

    for invoice in invoices:
        found = {
            'rectifying_invoice': _match(invoice, by_token.get(invoice.return_token, [])),
            'refactored_invoice': _match(invoice, by_token.get(invoice.refactored_token, [])),
            'rectified_invoice': _match(invoice, rectified_by_token.get(invoice.token, [])),
            'refactor_invoice': _match(invoice, refactor_by_token.get(invoice.token, [])),
        }
        relations[invoice.id] = {key: _link(other) for key, other in found.items() if other}
    return relations
