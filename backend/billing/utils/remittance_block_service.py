"""No domiciliar les factures d'un procés de facturació si el contracte ja deu diners.

Si el ConfigProject `block_remittance_if_unpaid` val `true`, les factures noves d'un procés
de facturació que s'havien de domiciliar (`DIRECT_DEBIT`) passen a «Pagament bancari» quan
el contracte ja té factures pendents de cobrar (vençudes o amb el rebut retornat, la mateixa
condició que les despeses d'impagat). Així no entren a cap remesa SEPA.

Per defecte val `false` i no es fa res.
"""
from coredata.models import ConfigProject
from contract.models import PaymentType

BLOCK_CONFIG_TOKEN = 'block_remittance_if_unpaid'
DEFAULT_DIRECT_DEBIT_TOKEN = 'DIRECT_DEBIT'
DEFAULT_BANK_PAYMENT_TOKEN = 'BANK_PAYMENT'


def _config_value(token):
    return ConfigProject.objects.filter(token=token).values_list('value', flat=True).first()


def is_block_remittance_if_unpaid_enabled():
    value = _config_value(BLOCK_CONFIG_TOKEN)
    return str(value or '').strip().lower() in ('true', '1', 'yes')


def contract_has_unpaid_invoices(contract):
    """Indica si el contracte té factures actives pendents de cobrar (vençudes o retornades)."""
    from billing.models import Invoice
    from billing.utils.unpaid_fee_service import UNPAID_STATUSES, unpaid_status_q

    query = unpaid_status_q(UNPAID_STATUSES)
    if not query:
        return False
    return Invoice.objects.filter(
        query, contract=contract, is_active=True, left_to_pay__gt=0,
    ).exists()


def blocked_remittance_payment_type(contract, payment_type):
    """Tipus de pagament «Pagament bancari» que ha de fer servir la factura nova, o None.

    Només retorna un tipus si el paràmetre està actiu, la factura es domiciliaria i el
    contracte té factures pendents de cobrar. Si no, la factura es queda com estava.
    """
    if not contract or not payment_type or not is_block_remittance_if_unpaid_enabled():
        return None
    direct_debit_token = _config_value('direct_debit_token') or DEFAULT_DIRECT_DEBIT_TOKEN
    if payment_type.token != direct_debit_token:
        return None
    if not contract_has_unpaid_invoices(contract):
        return None
    bank_payment_token = _config_value('bank_payment_token') or DEFAULT_BANK_PAYMENT_TOKEN
    return PaymentType.objects.filter(token=bank_payment_token).first()
