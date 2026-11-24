"""Cancel·lació de la domiciliació d'un contracte: factures obertes.

Quan un contracte deixa de pagar per domiciliació (p. ex. des de l'OV), les factures emeses que
encara s'esperaven cobrar per domiciliació passen també a la forma de pagament nova:

- factures actives, en estat confirmada, enviada o vençuda, amb forma de pagament
  domiciliació i import positiu (els abonaments no es toquen);
- amb algun rebut actiu pendent o retornat;
- sense cap rebut en una remesa pendent d'enviar (la remesa el cobrarà igualment).

El canvi queda a l'historial de cada factura (`apply_invoice_payment_method`) i el compte de
cobrament de la factura i dels rebuts no cobrats queda buit.
"""
from django.db.models import Exists, OuterRef, Q

from billing.models import Invoice, Payment
from billing.utils.invoice_service import apply_invoice_payment_method
from billing.utils.payment_service import disconnect_payment_signals, reconnect_payment_signals
from coredata.models import ConfigProject

DIRECT_DEBIT_TOKEN = 'DIRECT_DEBIT'


def _config_values(*tokens):
    values = ConfigProject.objects.filter(token__in=tokens).values_list('value', flat=True)
    return [value for value in values if value]


def direct_debit_open_invoices(contract):
    """Factures del contracte que encara s'esperen cobrar per domiciliació (veure el mòdul)."""
    issued_status_tokens = _config_values(
        'invoice_status_confirmed_token', 'invoice_status_sent_token', 'invoice_status_expired_token')
    open_payment_status_tokens = _config_values('payment_status_pending_token', 'payment_status_returned_token')
    if not issued_status_tokens or not open_payment_status_tokens:
        return Invoice.objects.none()

    open_payment = Payment.objects.filter(
        invoice=OuterRef('pk'), is_active=True, status__token__in=open_payment_status_tokens)
    payment_in_pending_remittance = Payment.objects.filter(
        invoice=OuterRef('pk'), remittances__isnull=False, remittances__sent_at__isnull=True)

    return (
        Invoice.objects.filter(
            Q(contract=contract)
            | Q(contract_request__contract=contract)
            | Q(contract_termination__contract=contract),
            is_active=True,
            status__token__in=issued_status_tokens,
            payment_type_token_final=DIRECT_DEBIT_TOKEN,
            total_final__gt=0,
        )
        .filter(Exists(open_payment))
        .exclude(Exists(payment_in_pending_remittance))
        .distinct()
    )


def move_direct_debit_invoices(contract, payment_type, user):
    """Passa les factures obertes domiciliades del contracte a `payment_type`, sense compte.

    Retorna les factures canviades. No fa res si el tipus nou és també domiciliació. S'ha de
    cridar dins d'una transacció.
    """
    if payment_type is None or payment_type.token == DIRECT_DEBIT_TOKEN:
        return []
    invoice_ids = list(direct_debit_open_invoices(contract).values_list('id', flat=True))
    if not invoice_ids:
        return []
    # Bloqueja els rebuts i després les factures, en el mateix ordre que `/ov/invoice/paid/`
    # (rebuts i, des dels senyals, la factura): un pagament alhora espera i no se sobreescriu.
    # Un cop bloquejades, es tornen a llegir i a filtrar per si han canviat mentrestant.
    list(Payment.objects.select_for_update().filter(invoice_id__in=invoice_ids).values_list('id', flat=True))
    invoices = list(
        Invoice.objects.select_for_update()
        .filter(id__in=invoice_ids)
        .filter(id__in=direct_debit_open_invoices(contract).values('id'))
        .order_by('id')
    )
    if not invoices:
        return []
    # Com al canvi de mètode des de la factura: només canvia el mètode, no genera moviments
    disconnect_payment_signals()
    try:
        for invoice in invoices:
            apply_invoice_payment_method(user, invoice, payment_type, None, None)
    finally:
        reconnect_payment_signals()
    return invoices
