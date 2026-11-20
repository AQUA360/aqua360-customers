"""Contractes de baixa d'una facturació: no es facturen d'ofici.

La facturació inclou les lectures d'un contracte de baixa anteriors a la data de baixa.
Abans de processar-la (o recalcular-la), l'usuari veu quins contractes de baixa té i tria
quins es facturen; la tria es desa al `payload` de l'element de la cua (BillingQueue), que es
manté si es reinicia, i la tasca no factura cap contracte de baixa que no hi sigui.
"""
from django.db.models import F, Q

from coredata.models import ConfigProject


TERMINATED_CONTRACT_IDS_KEY = 'terminated_contract_ids'


class TerminatedContractSelectionError(ValueError):
    """La tria de contractes de baixa no és vàlida (format o contractes que no hi són)."""


def _config_value(token):
    return ConfigProject.objects.get(token=token).value


def billable_readings_q():
    """Lectures que la facturació factura: contractes actius o de baixa posterior a la lectura."""
    active_token = _config_value('contract_active_token')
    terminated_token = _config_value('contract_terminated_status')
    completed_token = _config_value('contract_termination_completed_token')
    return (
        Q(contract__status__token=active_token) |
        (
            Q(contract__status__token=terminated_token) &
            Q(contract__contractterminationrequest__status__token=completed_token) &
            (
                Q(contract__contractterminationrequest__approved_at__date__gte=F('reading_date')) |
                Q(contract__contractterminationrequest__approved_at__isnull=True,
                  contract__contractterminationrequest__created_at__date__gte=F('reading_date'))
            )
        )
    )


def billable_readings(billing):
    """Lectures de la facturació que encara s'han de facturar."""
    return (
        billing.readings.filter(is_control=False, is_active=True, is_close=False)
        .filter(contract__block_billing=False)
        .filter(billable_readings_q())
        .exclude(Q(invoices__type_final='F') | Q(invoices__type_final='P'))
    )


def _recalculation_readings(billing):
    """Lectures que tornarà a facturar un recàlcul: també les de les factures excloses
    (que tornen al lot) i les que ara tenen una pre-factura del lot (que s'esborra)."""
    from billing.models import Invoice, Reading
    pending_token = _config_value('invoice_status_pending_token')
    blocking_invoices = Invoice.objects.filter(
        Q(type_final='F') | Q(type_final='P'),
    ).exclude(
        Q(billing=billing) | Q(billing__excluded_from=billing),
        status__token=pending_token,
    )
    return (
        Reading.objects.filter(Q(billing=billing) | Q(billing__excluded_from=billing))
        .filter(is_control=False, is_active=True, is_close=False)
        .filter(contract__block_billing=False)
        .filter(billable_readings_q())
        .exclude(invoices__in=blocking_invoices)
    )


def terminated_billable_contracts(billing, recalculation=False):
    """Contractes de baixa amb lectures per facturar en aquesta facturació."""
    from contract.models import Contract
    readings = _recalculation_readings(billing) if recalculation else billable_readings(billing)
    return Contract.objects.filter(
        id__in=readings.values('contract_id'),
        status__token=_config_value('contract_terminated_status'),
    ).distinct()


def resolve_terminated_contract_selection(billing, raw_ids, recalculation=False):
    """Valida la tria de l'usuari: una llista d'ids de contractes de baixa de la facturació.

    Buida o absent vol dir que no se'n factura cap.
    """
    if raw_ids in (None, ''):
        return []
    if not isinstance(raw_ids, list):
        raise TerminatedContractSelectionError('terminated_contract_ids must be a list')
    ids = set()
    for raw in raw_ids:
        # Només enters exactes: ni booleans, ni decimals (12.9 no pot passar per 12)
        if isinstance(raw, int) and not isinstance(raw, bool):
            ids.add(raw)
        elif isinstance(raw, str) and raw.strip().isdigit():
            ids.add(int(raw.strip()))
        else:
            raise TerminatedContractSelectionError('invalid contract id')
    if not ids:
        return []
    candidates = set(
        terminated_billable_contracts(billing, recalculation=recalculation).values_list('id', flat=True)
    )
    if ids - candidates:
        raise TerminatedContractSelectionError('contracts not terminated in this billing')
    return sorted(ids)


def queue_item_selection(queue_item_id):
    """Contractes de baixa triats en la confirmació que va crear l'element de la cua."""
    from billing.models import BillingQueue
    if not queue_item_id:
        return []
    payload = BillingQueue.objects.filter(id=queue_item_id).values_list('payload', flat=True).first()
    return (payload or {}).get(TERMINATED_CONTRACT_IDS_KEY) or []


def terminated_contract_ids_to_skip(contract_ids, selected_ids):
    """Dels contractes a facturar, els de baixa que l'usuari no ha triat."""
    from contract.models import Contract
    if not contract_ids:
        return set()
    selected = set(selected_ids or [])
    terminated = Contract.objects.filter(
        id__in=contract_ids, status__token=_config_value('contract_terminated_status'),
    ).values_list('id', flat=True)
    return set(terminated) - selected
