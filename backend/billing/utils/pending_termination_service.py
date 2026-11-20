"""Contractes amb la baixa iniciada (esborrany o pendent) i l'alta que els substitueix.

En un canvi de titular, el contracte de sortida continua actiu fins que es finalitza
la baixa. Mentrestant, al mateix punt hi ha dos contractes actius: les lectures noves
poden acabar al de sortida i la facturació el factura sense saber-ho. Aquí hi ha:

- la detecció (per a l'avís de la facturació i per triar el contracte de les lectures);
- el traspàs d'una prefactura del contracte de sortida a la nova alta.
"""
from django.db import transaction
from django.db.models import Q

from coredata.models import ConfigProject

PENDING_TERMINATION_WARNING_CONFIG = 'invoice_warning_pending_termination'
TERMINATED_CONTRACT_WARNING_CONFIG = 'invoice_warning_terminated_contract'


class PendingTerminationTransferError(Exception):
    """Motiu (codi) pel qual no es pot passar una prefactura a la nova alta."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _config_value(token):
    return ConfigProject.objects.filter(token=token).values_list('value', flat=True).first()


def open_termination_status_tokens():
    """Estats d'una baixa iniciada però no finalitzada: esborrany i pendent."""
    return [
        value for value in (
            _config_value('contract_termination_draft'),
            _config_value('contract_termination_pending_token'),
        ) if value
    ]


def get_open_termination(contract):
    """Baixa iniciada i no finalitzada del contracte (la més recent), o None."""
    if contract is None:
        return None
    status_tokens = open_termination_status_tokens()
    if not status_tokens:
        return None
    from contract.models import ContractTerminationRequest
    return (
        ContractTerminationRequest.objects.filter(contract=contract, status__token__in=status_tokens)
        .order_by('-created_at', '-id')
        .first()
    )


def get_successor_contract(contract, termination=None):
    """Contracte actiu de l'alta vinculada a la baixa iniciada del contracte, o None."""
    termination = termination or get_open_termination(contract)
    if termination is None:
        return None
    from contract.models import Contract
    active_token = _config_value('contract_active_token')
    successors = Contract.objects.filter(
        contract_request__contract_termination_requests=termination,
        is_active=True,
    ).exclude(id=contract.id)
    if active_token:
        successors = successors.filter(status__token=active_token)
    return successors.order_by('-id').first()


def get_pending_termination_warning():
    from billing.models import InvoiceWarning
    token = _config_value(PENDING_TERMINATION_WARNING_CONFIG)
    if not token:
        return None
    return InvoiceWarning.objects.filter(token=token).first()


def get_terminated_contract_warning():
    """Avís de les factures de contractes de baixa (la facturació les deixa excloses)."""
    from billing.models import InvoiceWarning
    token = _config_value(TERMINATED_CONTRACT_WARNING_CONFIG)
    if not token:
        return None
    return InvoiceWarning.objects.filter(token=token).first()


def pending_termination_warning_for(contract):
    """L'avís de baixa pendent si el contracte en té una d'iniciada; si no, None."""
    if get_open_termination(contract) is None:
        return None
    return get_pending_termination_warning()


def contract_ids_with_open_termination(contract_ids):
    """Dels contractes donats, els que tenen una baixa iniciada (una sola consulta per a un lot)."""
    status_tokens = open_termination_status_tokens()
    if not status_tokens or not contract_ids:
        return set()
    from contract.models import ContractTerminationRequest
    return set(
        ContractTerminationRequest.objects.filter(
            contract_id__in=contract_ids, status__token__in=status_tokens,
        ).values_list('contract_id', flat=True)
    )


def is_pending_termination_warning(warning):
    if warning is None:
        return False
    return warning.token == _config_value(PENDING_TERMINATION_WARNING_CONFIG)


def outgoing_contract_ids_for_supply_point(supply_point, reading_date):
    """Contractes del punt amb la baixa iniciada que ja tenen una alta activa al mateix
    punt en vigor a la data de la lectura: la lectura ja és del contracte nou."""
    from contract.models import Contract
    status_tokens = open_termination_status_tokens()
    if supply_point is None or reading_date is None or not status_tokens:
        return set()
    candidates = Contract.objects.filter(
        Q(supply_points=supply_point) | Q(supply_point_default=supply_point),
        contractterminationrequest__status__token__in=status_tokens,
    ).distinct()
    outgoing = set()
    for contract in candidates:
        successor = get_successor_contract(contract)
        if successor is None:
            continue
        if not (
            successor.supply_point_default_id == supply_point.id
            or successor.supply_points.filter(id=supply_point.id).exists()
        ):
            continue
        if successor.registration_date and successor.registration_date > reading_date:
            continue
        outgoing.add(contract.id)
    return outgoing


def _initial_reading(successor, meter_id):
    from billing.models import Reading
    return (
        Reading.objects.filter(contract=successor, meter_id=meter_id, is_initial=True, is_active=True)
        .order_by('-reading_date', '-id')
        .first()
    )


def bill_invoice_to_successor(invoice_id):
    """Passa una prefactura del contracte de sortida a la nova alta.

    Esborra la prefactura, mou les seves lectures al contracte nou (encadenades a la
    lectura inicial de l'alta) i en genera una de nova a la mateixa facturació.
    Només es pot fer si tot el consum facturat és posterior a la lectura inicial
    de l'alta: si no, part del consum és del titular anterior.
    """
    from billing.models import Invoice, Reading
    from billing.utils.invoice_service import generate_consumption_invoice_multiple
    from billing.utils.recalculate_invoice_service import (
        _assert_invoice_is_recalculable,
        _get_invoice_warning,
        _get_period_months,
    )

    with transaction.atomic():
        invoice = (
            Invoice.objects.select_for_update(of=('self',))
            .select_related('billing', 'billing__biller', 'contract', 'status')
            .get(id=invoice_id)
        )
        try:
            _assert_invoice_is_recalculable(invoice)
        except ValueError:
            raise PendingTerminationTransferError('not_pre_invoice')
        if not invoice.billing_id:
            raise PendingTerminationTransferError('not_in_billing')

        contract = invoice.contract
        termination = get_open_termination(contract)
        if termination is None:
            raise PendingTerminationTransferError('no_open_termination')
        successor = get_successor_contract(contract, termination)
        if successor is None:
            raise PendingTerminationTransferError('no_successor')
        if successor.block_billing:
            raise PendingTerminationTransferError('successor_blocked')

        readings = list(
            invoice.readings.filter(is_control=False, is_active=True).select_related('previous_reading')
        )
        if not readings:
            raise PendingTerminationTransferError('no_readings')

        successor_supply_point_ids = set(successor.supply_points.values_list('id', flat=True))
        if successor.supply_point_default_id:
            successor_supply_point_ids.add(successor.supply_point_default_id)

        chained = []
        for reading in readings:
            if reading.contract_id != contract.id:
                raise PendingTerminationTransferError('foreign_reading')
            if reading.supply_point_id not in successor_supply_point_ids:
                raise PendingTerminationTransferError('other_supply_point')
            initial = _initial_reading(successor, reading.meter_id)
            if initial is None:
                raise PendingTerminationTransferError('no_initial_reading')
            if reading.reading_date < initial.reading_date:
                raise PendingTerminationTransferError('reading_before_successor')
            previous = reading.previous_reading
            if previous is not None and previous.contract_id != successor.id:
                # El consum s'ha calculat des d'una lectura del contracte de sortida: només
                # és el mateix si és la de tall (mateixa data i valor que la inicial).
                if previous.reading_date != initial.reading_date or previous.reading_value != initial.reading_value:
                    raise PendingTerminationTransferError('consumption_before_successor')
            if Reading.objects.filter(
                contract=successor, meter_id=reading.meter_id, reading_date=reading.reading_date,
                is_control=False, is_active=True,
            ).exists():
                raise PendingTerminationTransferError('successor_has_reading')
            chained.append((reading, initial))

        billing = invoice.billing
        period_months = _get_period_months(invoice)
        invoice.delete()

        for reading, initial in chained:
            reading.contract = successor
            if reading.previous_reading_id is None or reading.previous_reading.contract_id != successor.id:
                reading.previous_reading = initial
            reading.save(update_fields=['contract', 'previous_reading', 'updated_at'])

        moved = Reading.objects.filter(id__in=[reading.id for reading, _ in chained])
        new_invoice = generate_consumption_invoice_multiple(
            successor, list(moved), billing.name, billing=billing, period_months=period_months,
        )
        if not new_invoice:
            raise PendingTerminationTransferError('not_generated')
        if new_invoice.billing_id != billing.id:
            new_invoice.billing = billing
            new_invoice.save(update_fields=['billing'])

        new_invoice.warning = _get_invoice_warning(new_invoice, [successor])
        new_invoice.save(update_fields=['warning'])
        return new_invoice
