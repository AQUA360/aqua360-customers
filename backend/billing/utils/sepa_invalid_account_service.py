"""Retorns SEPA per compte invàlid (IBAN incorrecte, compte tancat o bloquejat...).

Si el banc retorna un rebut amb un dels motius configurats a
`sepa_invalid_account_reject_tokens` (llista separada per comes), tornar a domiciliar a aquell
compte no té sentit. Valor per defecte (motius ISO 20022):

- AC01: número de compte incorrecte / IBAN invàlid
- AC04: compte tancat
- AC06: compte bloquejat
- AC13: tipus de compte invàlid
- AG01: operació no permesa (el compte no admet domiciliacions)
- BE06: deutor desconegut (identificador del deutor invàlid)
- MD07: titular difunt
- RC01: identificador del banc incorrecte / BIC invàlid

En aplicar el retorn:

1. Es desactiven els comptes del titular amb aquell IBAN (`PersonBank`) i les formes de
   pagament que els fan servir (`GeneralPayment`).
2. Els contractes que tenien aquestes formes de pagament passen a una forma de pagament
   nova de tipus «Pagament bancari» sense IBAN (queda registrat a `ContractDataChange`).
3. Les factures emeses d'aquests contractes que es domiciliaven a aquell IBAN, amb rebuts
   pendents o retornats i sense cap rebut en una remesa pendent d'enviar, passen a
   «Pagament bancari» sense IBAN (queda registrat a l'historial de la factura).

Si el paràmetre no existeix o és buit, no es fa res.
"""
import logging

from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Replace, Upper
from django.db.models import Value
from django.utils import timezone

from billing.models import GeneralPayment, Invoice
from billing.utils.invoice_service import apply_invoice_payment_method
from billing.utils.payment_service import disconnect_payment_signals, reconnect_payment_signals
from contract.models import Contract, ContractDataChange, PaymentType
from coredata.models import ConfigProject, PersonBank

logger = logging.getLogger(__name__)

INVALID_ACCOUNT_CONFIG_TOKEN = 'sepa_invalid_account_reject_tokens'
DIRECT_DEBIT_TOKEN = 'DIRECT_DEBIT'
DEFAULT_BANK_PAYMENT_TOKEN = 'BANK_PAYMENT'


def normalize_iban(iban):
    return (iban or '').replace(' ', '').upper()


def get_invalid_account_reject_tokens():
    value = ConfigProject.objects.filter(token=INVALID_ACCOUNT_CONFIG_TOKEN).values_list('value', flat=True).first()
    return {token.strip().upper() for token in (value or '').split(',') if token.strip()}


def is_invalid_account_reject_token(reject_token, tokens=None):
    if not reject_token:
        return False
    if tokens is None:
        tokens = get_invalid_account_reject_tokens()
    return str(reject_token).strip().upper() in tokens


def _config_value(token):
    return ConfigProject.objects.filter(token=token).values_list('value', flat=True).first()


def _bank_payment_type():
    token = _config_value('bank_payment_token') or DEFAULT_BANK_PAYMENT_TOKEN
    return PaymentType.objects.filter(token=token).first()


def _normalized(field):
    return Upper(Replace(field, Value(' '), Value('')))


def resolve_payment_contract(payment):
    """El contracte del pagament retornat (factura, sol·licitud, baixa o dipòsit)."""
    invoice = payment.invoice
    if invoice:
        if invoice.contract_id:
            return invoice.contract
        if invoice.contract_request_id:
            return Contract.objects.filter(contract_request=invoice.contract_request).first()
        if invoice.contract_termination_id:
            return invoice.contract_termination.contract
    if payment.commitment_deposit_id:
        return payment.commitment_deposit.contract
    return getattr(payment, 'contract', None)


def _deactivate_person_banks(person_banks, now):
    for person_bank in person_banks:
        was_default = person_bank.is_default
        person_bank.is_active = False
        person_bank.is_default = False
        person_bank.deactivated_at = now
        person_bank._skip_signal = True
        person_bank.save(update_fields=['is_active', 'is_default', 'deactivated_at', 'updated_at'])
        # Com quan es desactiva un compte a mà: un altre compte actiu del titular passa a ser el principal
        if was_default and person_bank.person_id:
            replacement = PersonBank.objects.filter(
                person_id=person_bank.person_id, is_active=True).exclude(pk=person_bank.pk).order_by('-created_at').first()
            if replacement:
                replacement.is_default = True
                replacement._skip_signal = True
                replacement.save(update_fields=['is_default', 'updated_at'])


def _replace_contract_payments(general_payments, bank_payment, user, motive):
    """Cada forma de pagament desactivada es substitueix per una de «Pagament bancari» sense IBAN."""
    changed_contracts = []
    for general_payment in general_payments:
        contracts = list(Contract.objects.filter(payment=general_payment))
        general_payment.is_active = False
        general_payment.save(update_fields=['is_active', 'updated_at'])
        if not contracts:
            continue
        new_payment = GeneralPayment.objects.create(
            token=f"{general_payment.token or contracts[0].token}_{bank_payment.token}",
            type=bank_payment,
            # Les dades de facturació electrònica no depenen del compte bancari
            dir3=general_payment.dir3,
            accounting_office=general_payment.accounting_office,
            managing_body=general_payment.managing_body,
            processing_unit=general_payment.processing_unit,
            command=general_payment.command,
            record=general_payment.record,
        )
        for contract in contracts:
            ContractDataChange.objects.create(
                contract=contract,
                previous_payment=general_payment.IBAN,
                new_payment=None,
                previous_payment_type=general_payment.type,
                new_payment_type=bank_payment,
                new_general_payment=new_payment,
                reject_motive=motive,
                user=user,
                approved_at=timezone.now(),
            )
            contract.payment = new_payment
            contract.save(update_fields=['payment', 'updated_at'])
            changed_contracts.append(contract)
    return changed_contracts


def _eligible_invoices(contracts, extra_invoice_ids, iban):
    """Factures emeses domiciliades a l'IBAN, amb rebuts pendents o retornats i fora de remeses pendents."""
    issued_status_tokens = [value for value in (
        _config_value('invoice_status_confirmed_token'),
        _config_value('invoice_status_sent_token'),
        _config_value('invoice_status_expired_token'),
    ) if value]
    open_payment_status_tokens = [value for value in (
        _config_value('payment_status_pending_token'),
        _config_value('payment_status_returned_token'),
    ) if value]
    if not issued_status_tokens or not open_payment_status_tokens:
        return Invoice.objects.none()

    scope = Q(id__in=extra_invoice_ids)
    if contracts:
        scope |= (
            Q(contract__in=contracts)
            | Q(contract_request__contract__in=contracts)
            | Q(contract_termination__contract__in=contracts)
        )

    return (
        Invoice.objects.filter(scope)
        .filter(
            is_active=True,
            status__token__in=issued_status_tokens,
            payment_type_token_final=DIRECT_DEBIT_TOKEN,
            payments__status__token__in=open_payment_status_tokens,
        )
        .annotate(normalized_bank=_normalized('payment_bank_final'))
        .filter(Q(normalized_bank=iban) | Q(payment_bank_final__isnull=True) | Q(payment_bank_final=''))
        # Un rebut que ja és en una remesa pendent d'enviar es deixa com està: la remesa el cobrarà
        .exclude(payments__remittances__id__isnull=False, payments__remittances__sent_at__isnull=True)
        .distinct()
    )


def handle_invalid_account_return(payment, motive, iban, user=None, tokens=None):
    """Aplica la cascada de compte invàlid per al pagament retornat. Retorna un resum o None."""
    if not motive or not is_invalid_account_reject_token(motive.token, tokens):
        return None
    iban = normalize_iban(iban)
    if not iban:
        return None
    bank_payment = _bank_payment_type()
    if not bank_payment:
        logger.warning("No es pot aplicar el retorn per compte invàlid: falta el tipus de pagament bancari")
        return None

    contract = resolve_payment_contract(payment)
    holder_id = contract.holder_id if contract else None

    with transaction.atomic():
        person_banks = PersonBank.objects.none()
        if holder_id:
            person_banks = (
                PersonBank.objects.filter(person_id=holder_id, is_active=True)
                .annotate(normalized_iban=_normalized('iban'))
                .filter(normalized_iban=iban)
            )
        # El compte de la forma de pagament del contracte, encara que no sigui del titular
        if contract and contract.payment_id and contract.payment.IBAN_id:
            contract_bank = (
                PersonBank.objects.filter(id=contract.payment.IBAN_id, is_active=True)
                .annotate(normalized_iban=_normalized('iban'))
                .filter(normalized_iban=iban)
            )
            person_banks = person_banks | contract_bank
        person_banks = list(person_banks.distinct())

        general_payments = list(GeneralPayment.objects.filter(
            IBAN__in=person_banks, is_active=True, type__token=DIRECT_DEBIT_TOKEN))

        now = timezone.now()
        _deactivate_person_banks(person_banks, now)
        changed_contracts = _replace_contract_payments(general_payments, bank_payment, user, motive)

        affected_contracts = list({c.id: c for c in changed_contracts + ([contract] if contract else [])}.values())
        extra_invoice_ids = [payment.invoice_id] if payment.invoice_id else []
        invoices = list(_eligible_invoices(affected_contracts, extra_invoice_ids, iban))

        disconnect_payment_signals()
        try:
            for invoice in invoices:
                apply_invoice_payment_method(user, invoice, bank_payment, None, None)
        finally:
            reconnect_payment_signals()

    return {
        'payment_id': payment.id,
        'motive': motive.token,
        'deactivated_banks': len(person_banks),
        'deactivated_payments': len(general_payments),
        'contracts': [c.token for c in changed_contracts],
        'invoices': [i.serie_final or i.token for i in invoices],
    }


def invalid_account_payment_alert(contract):
    """Avís per a la fitxa del contracte: domiciliació anul·lada per un retorn de compte invàlid.

    Només surt mentre el contracte continua amb la forma de pagament que va crear el retorn i
    aquesta continua sent «Pagament bancari» sense IBAN: qualsevol canvi posterior (un altre
    compte, una altra forma de pagament o un IBAN nou) el fa desaparèixer. Fa com a molt una
    consulta i només s'ha de fer servir en serialitzadors d'un sol contracte.
    """
    payment = contract.payment if contract.payment_id else None
    if not payment or payment.IBAN_id or not payment.type_id:
        return None
    bank_payment_token = _config_value('bank_payment_token') or DEFAULT_BANK_PAYMENT_TOKEN
    if payment.type.token != bank_payment_token:
        return None
    data_change = (
        ContractDataChange.objects.filter(
            contract_id=contract.id, new_general_payment_id=payment.id, reject_motive__isnull=False)
        .select_related('reject_motive', 'previous_payment')
        .order_by('-created_at')
        .first()
    )
    if not data_change:
        return None
    return {
        'date': data_change.created_at,
        'motive_token': data_change.reject_motive.token,
        'motive_name': data_change.reject_motive.name,
        'previous_iban': data_change.previous_payment.iban if data_change.previous_payment else None,
    }
