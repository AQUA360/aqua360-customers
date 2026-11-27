"""Avisos de canvis de mètode de pagament que el sistema fa sol.

Hi ha dos casos, que queden marcats a l'historial de la factura (`LogInvoiceDataChange.auto_reason`):

- Retorn SEPA per compte invàlid (`sepa_invalid_account_service`): les factures obertes que es
  domiciliaven al compte retornat passen a «Pagament bancari».
- Paràmetre `block_remittance_if_unpaid` (`remittance_block_service`): el procés de facturació no
  domicilia les factures noves d'un contracte que ja té factures pendents de cobrar. El contracte
  continua domiciliat, així que l'avís ha de sortir també a la fitxa del contracte.

L'avís d'una factura només surt mentre la factura conserva el mètode de pagament que hi va posar el
sistema (qualsevol canvi posterior, a mà o automàtic, el treu) i no està cobrada ni anul·lada.
"""
from coredata.models import ConfigProject
from logger.models import LogInvoiceDataChange


def _closed_status_tokens():
    """Estats de factura en què ja no té sentit avisar: cobrada o anul·lada."""
    tokens = ConfigProject.objects.filter(
        token__in=['invoice_status_paid_token', 'invoice_status_cancelled_token'],
    ).values_list('value', flat=True)
    return {token for token in tokens if token}


def _last_payment_type_change(invoice):
    """L'últim canvi de mètode de pagament de l'historial de la factura, o None."""
    return (
        LogInvoiceDataChange.objects.filter(object_id=invoice.pk, current_payment_type__isnull=False)
        .exclude(current_payment_type='')
        .select_related('reject_motive')
        .order_by('-timestamp', '-id')
        .first()
    )


def invoice_payment_method_alert(invoice, closed_status_tokens=None):
    """Avís per a la fitxa de la factura si el sistema n'ha canviat el mètode de pagament, o None."""
    if not invoice or not invoice.pk or not invoice.is_active:
        return None
    if closed_status_tokens is None:
        closed_status_tokens = _closed_status_tokens()
    if invoice.status_id and invoice.status.token in closed_status_tokens:
        return None
    change = _last_payment_type_change(invoice)
    if not change or not change.auto_reason:
        return None
    # Si la factura ja no té el mètode que hi va posar el sistema, algú l'ha tornat a canviar
    if change.current_payment_type != invoice.payment_type_final:
        return None
    motive = change.reject_motive
    return {
        'reason': change.auto_reason,
        'date': change.timestamp,
        'previous_payment_type': change.previous_payment_type,
        'previous_iban': change.previous_iban,
        'motive_token': motive.token if motive else None,
        'motive_name': motive.name if motive else None,
    }


def contract_remittance_blocked_alert(contract):
    """Avís per a la fitxa del contracte: factures pendents que el procés de facturació no ha domiciliat.

    Retorna None si no n'hi ha cap. Només s'ha de fer servir en serialitzadors d'un sol contracte.
    """
    if not contract or not contract.pk:
        return None
    from billing.models import Invoice

    invoice_ids = (
        LogInvoiceDataChange.objects.filter(
            auto_reason=LogInvoiceDataChange.AUTO_REASON_REMITTANCE_BLOCKED,
            object__contract_id=contract.pk,
            object__is_active=True,
        )
        .values_list('object_id', flat=True)
        .distinct()
    )
    closed_status_tokens = _closed_status_tokens()
    invoices = []
    last_date = None
    for invoice in Invoice.objects.filter(id__in=invoice_ids).select_related('status').order_by('-issue_date', '-id'):
        alert = invoice_payment_method_alert(invoice, closed_status_tokens)
        if not alert or alert['reason'] != LogInvoiceDataChange.AUTO_REASON_REMITTANCE_BLOCKED:
            continue
        invoices.append({'id': invoice.id, 'number': invoice.serie_final or invoice.token})
        if last_date is None or alert['date'] > last_date:
            last_date = alert['date']
    if not invoices:
        return None
    return {'count': len(invoices), 'date': last_date, 'invoices': invoices}
