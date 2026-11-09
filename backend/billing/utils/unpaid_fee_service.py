"""Despeses d'impagat de factures vençudes o amb el rebut retornat.

Operació manual de la llista de factures: es filtren les factures pendents de
cobrar (vençudes, o amb un retorn SEPA sense despeses) i s'hi aplica una
factura de despeses amb les tarifes triades, com fa `invoice_return_charge()`
en processar un retorn.

Només està disponible si el ConfigProject `unpaid_fee_operation_enabled` val
`true`.
"""

from django.db.models import Q

from coredata.models import ConfigProject
from pricing.models import PriceRate


ENABLED_CONFIG_TOKEN = 'unpaid_fee_operation_enabled'

# El mateix títol que les despeses dels retorns SEPA.
FEE_INVOICE_TITLE = 'RECLAMACIÓ DE SERVEI'

UNPAID_STATUS_EXPIRED = 'expired'
UNPAID_STATUS_RETURNED = 'returned'

# Una execució que no ha arrencat en aquestes hores es dona per perduda.
STALE_RUN_HOURS = 12

def _config_value(token):
    return ConfigProject.objects.filter(token=token).values_list('value', flat=True).first()


def is_unpaid_fee_operation_enabled():
    value = _config_value(ENABLED_CONFIG_TOKEN)
    return str(value or '').strip().lower() in ('true', '1', 'yes')


def default_unpaid_fee_price_rate():
    """La tarifa de despeses de devolució configurada, si n'hi ha."""
    token = _config_value('invoice_return_price_rate_token')
    if not token:
        return None
    return PriceRate.objects.filter(token=token, is_active=True).first()


def unpaid_status_q(kinds):
    """Factures pendents de cobrar segons el motiu: vençudes o amb el rebut retornat."""
    query = Q()
    if UNPAID_STATUS_EXPIRED in kinds:
        expired_token = _config_value('invoice_status_expired_token')
        if expired_token:
            query |= Q(status__token=expired_token)
    if UNPAID_STATUS_RETURNED in kinds:
        returned_token = _config_value('payment_status_returned_token')
        if returned_token:
            query |= Q(payments__status__token=returned_token)
    return query


def fee_invoices(price_rate_ids):
    """Factures que porten alguna línia d'aquestes tarifes."""
    from billing.models import Invoice
    return Invoice.objects.filter(line_items__price_rate__id__in=price_rate_ids)


def with_fee_ids(price_rate_ids):
    """Factures que ja són despeses o que ja en tenen alguna a la cadena de filles.

    Les despeses es pengen al final de la cadena (`invoice_return_charge()`),
    així que es puja des de cada despesa fins a l'arrel. Es retornen els ids ja
    calculats: com a subconsulta amb joins encadenats, dins del llistat, la
    consulta passava de segons.
    """
    from billing.models import Invoice
    managed = set(fee_invoices(price_rate_ids).values_list('id', flat=True))
    current = managed
    while current:
        current = set(
            Invoice.objects.filter(id__in=current, parent_invoice__isnull=False)
            .values_list('parent_invoice_id', flat=True)
        ) - managed
        managed |= current
    return managed


def vulnerable_q():
    """Contractes amb el titular (o l'inquilí, si el titular és jurídic) vulnerable o en risc."""
    return (
        Q(contract__holder__is_juridic=False, contract__holder__vulnerability_level__gt=0)
        | Q(contract__holder__is_juridic=True, contract__tenant__vulnerability_level__gt=0)
    )


def terminated_contract_q():
    """Contractes amb la baixa finalitzada."""
    from contract.models import ContractTerminationRequest
    completed_token = _config_value('contract_termination_completed_token')
    if not completed_token:
        return None
    terminated_contract_ids = ContractTerminationRequest.objects.filter(
        is_active=True, status__token=completed_token,
    ).values('contract_id')
    return Q(contract__id__in=terminated_contract_ids) | Q(contract_termination__status__token=completed_token)


def open_claim_q():
    """Factures amb algun rebut dins d'una gestió d'impagats oberta (pendent o acceptada)."""
    open_tokens = list(
        ConfigProject.objects.filter(
            token__in=['claim_request_status_accepted_token', 'claim_request_status_pending_token']
        ).values_list('value', flat=True)
    )
    if not open_tokens:
        return None
    return Q(payments__claim_requests__claim_request__status__token__in=open_tokens)


def active_run():
    """L'execució en curs, si n'hi ha; només se'n permet una alhora.

    Si la tasca ha fallat sense poder-ho apuntar, o fa hores que no arrenca
    (worker aturat), es dona per fallida perquè no bloquegi la pantalla.
    """
    from datetime import timedelta
    from celery.result import AsyncResult
    from django.utils import timezone
    from billing.models import UnpaidFeeRun
    run = UnpaidFeeRun.objects.filter(status=UnpaidFeeRun.STATUS_RUNNING).select_related('created_by').first()
    if not run:
        return None
    state = AsyncResult(run.task_id).state if run.task_id else 'PENDING'
    stale = state == 'PENDING' and run.created_at < timezone.now() - timedelta(hours=STALE_RUN_HOURS)
    if state in ('FAILURE', 'REVOKED') or stale:
        finish_run(run.id, error='Task interrupted')
        return None
    return run


def finish_run(run_id, result=None, error=None):
    from django.utils import timezone
    from billing.models import UnpaidFeeRun
    UnpaidFeeRun.objects.filter(id=run_id).update(
        status=UnpaidFeeRun.STATUS_FAILED if error else UnpaidFeeRun.STATUS_DONE,
        result={'error': error} if error else result,
        finished_at=timezone.now(),
    )


def serialize_run(run):
    if not run:
        return None
    user = run.created_by
    return {
        'id': run.id,
        'task_id': run.task_id,
        'status': run.status,
        'invoice_count': run.invoice_count,
        'price_rates': [price_rate.name or price_rate.token for price_rate in run.price_rates.all()],
        'result': run.result,
        'created_by': (user.get_full_name() or user.username) if user else None,
        'created_at': run.created_at,
        'finished_at': run.finished_at,
    }


def root_invoice(invoice):
    while invoice.parent_invoice_id:
        invoice = invoice.parent_invoice
    return invoice


def generate_unpaid_fee_invoices(invoice_ids, price_rate_ids, on_progress=None):
    """Crea una factura de despeses per a cada factura.

    Les despeses van a la factura arrel, com en els retorns, i no es tornen a
    crear si la cadena ja en té amb aquestes tarifes (p. ex. si s'ha llançat dos
    cops). Un error en una factura no atura la resta.
    """
    from billing.models import Invoice
    from billing.utils.invoice_service import invoice_return_charge

    price_rates = list(PriceRate.objects.filter(id__in=price_rate_ids))
    if not price_rates:
        raise ValueError("No price rates")
    price_rate_ids = [price_rate.id for price_rate in price_rates]

    invoices = list(Invoice.objects.filter(id__in=invoice_ids).select_related('parent_invoice'))
    total = len(invoices)
    processed_root_ids = set()
    managed_ids = with_fee_ids(price_rate_ids)
    created, skipped, errors = [], 0, []

    for index, invoice in enumerate(invoices, start=1):
        root = root_invoice(invoice)
        if root.id in processed_root_ids:
            skipped += 1
        elif root.id in managed_ids:
            processed_root_ids.add(root.id)
            skipped += 1
        else:
            processed_root_ids.add(root.id)
            try:
                fee_invoice = invoice_return_charge(root, FEE_INVOICE_TITLE, fee_price_rates=price_rates)
                created.append(fee_invoice.id)
            except Exception as e:
                errors.append({'invoice': root.serie_final or root.token, 'error': str(e)})
        if on_progress:
            on_progress(index, total)

    return {'created': len(created), 'created_ids': created, 'skipped': skipped, 'errors': errors}
