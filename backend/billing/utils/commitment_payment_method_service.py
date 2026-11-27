"""
Canvi de la forma de pagament d'un rebut pendent d'un compromís de pagament.

Els rebuts d'un compromís (pagaments amb `commitment_deposit` i sense factura) es
generen a partir d'un termini (`PaymentCommitment` guia) i fins ara no se'n podia
canviar la forma de pagament. Aquest servei la canvia sense generar moviments ni
canviar l'estat del rebut:

- Només rebuts actius, pendents de cobrar, que no siguin en una remesa pendent
  d'enviar ni en un pagament agrupat obert.
- Actualitza també el termini del compromís d'on surt el rebut.
- A les transferències, el compte és un dels comptes actius de l'empresa del
  contracte; a les domiciliacions, un compte de les persones del contracte.
- Treu el rebut de "marcat per remesar" i en deixa constància a l'historial.
"""
from django.db import transaction
from django.utils import timezone

from billing.models import Payment, PaymentCommitment
from billing.utils.remittance_mark_service import payment_in_pending_remittance
from contract.models import PaymentType
from coredata.models import ConfigProject, PersonBank
from logger.models import LogPaymentStatusChange
from service.models import CompanyBank

# El saldo és una forma de cobrar (descompta la guardiola), no una forma de pagament
# pendent; la factura electrònica no s'aplica als rebuts d'un compromís.
EXCLUDED_PAYMENT_TYPE_TOKENS = ('BALANCE', 'ELECTRONIC_INVOICE')


ERROR_MESSAGES = {
    'not_commitment': "Només es pot canviar la forma de pagament dels rebuts d'un compromís de pagament.",
    'inactive': "El rebut no és actiu.",
    'not_pending': "Només es pot canviar la forma de pagament d'un rebut pendent de cobrar.",
    'pending_remittance': "El rebut és en una remesa pendent d'enviar: primer cal treure'l de la remesa.",
    'joined_payment': "El rebut és en un pagament agrupat obert.",
    'invalid_payment_type': "Cal triar una forma de pagament vàlida.",
    'same_payment_type': "El rebut ja té aquesta forma de pagament.",
    'person_bank_required': "Cal triar un compte d'una persona del contracte per domiciliar el rebut.",
    'company_bank_required': "Cal triar un compte actiu de l'empresa del contracte.",
}


class CommitmentPaymentMethodError(Exception):
    """Error de validació: `code` és una clau d'`ERROR_MESSAGES`."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def error_message(code):
    """Missatge fix per a l'usuari (mai el text de l'excepció)."""
    return ERROR_MESSAGES.get(code, "No es pot canviar la forma de pagament del rebut.")


def _config(token):
    return ConfigProject.objects.get(token=token).value


def is_commitment_payment(payment):
    return bool(payment.commitment_deposit_id) and not payment.invoice_id


def check_commitment_payment_changeable(payment):
    """Llança `CommitmentPaymentMethodError` si no es pot canviar la forma de pagament."""
    if not is_commitment_payment(payment):
        raise CommitmentPaymentMethodError('not_commitment')
    if not payment.is_active:
        raise CommitmentPaymentMethodError('inactive')
    if not payment.status or payment.status.token != _config('payment_status_pending_token'):
        raise CommitmentPaymentMethodError('not_pending')
    if payment_in_pending_remittance(payment):
        raise CommitmentPaymentMethodError('pending_remittance')
    closed_joined_tokens = [
        _config('joined_payment_status_paid_token'),
        _config('joined_payment_status_cancelled_token'),
    ]
    if payment.joined_payments.filter(is_active=True).exclude(status__token__in=closed_joined_tokens).exists():
        raise CommitmentPaymentMethodError('joined_payment')


def get_contract_company_banks(contract):
    """Comptes actius amb IBAN de l'empresa del contracte."""
    if not contract or not contract.company_id:
        return CompanyBank.objects.none()
    return CompanyBank.objects.filter(
        company_id=contract.company_id, is_active=True, iban__isnull=False,
    ).exclude(iban='').order_by('id')


def get_contract_person_banks(contract):
    """Comptes amb IBAN de les persones del contracte (titular, propietari, llogater i
    qui paga la domiciliació actual)."""
    if not contract:
        return PersonBank.objects.none()
    person_ids = {contract.holder_id, contract.owner_id, contract.tenant_id}
    general_payment = contract.payment
    if general_payment and general_payment.IBAN_id and general_payment.IBAN.person_id:
        person_ids.add(general_payment.IBAN.person_id)
    person_ids.discard(None)
    return PersonBank.objects.filter(
        person_id__in=person_ids, iban__isnull=False,
    ).exclude(iban='').order_by('id')


def get_available_payment_types():
    return PaymentType.objects.exclude(token__in=EXCLUDED_PAYMENT_TYPE_TOKENS).order_by('id')


def find_guide_commitment(payment):
    """Termini (guia) del compromís d'on surt el rebut.

    No hi ha relació directa: en generar el rebut, el termini li copia el venciment,
    l'import i la forma de pagament (`add_wallet_payment`), així que es fa coincidir per
    compromís i venciment i, amb més d'un candidat, també per import i forma de pagament.
    Si encara en queden diversos, són terminis iguals (mateix venciment, import i forma):
    se n'agafa el primer, i el rebut germà trobarà l'altre perquè aquest ja haurà canviat
    de forma de pagament.
    """
    if not payment.due_date:
        return None
    candidates = PaymentCommitment.objects.select_for_update().filter(
        commitment_deposit_id=payment.commitment_deposit_id,
        is_guide=True,
        due_date=payment.due_date,
    ).order_by('id')
    for narrower in (
        {'amount': payment.amount},
        {'payment_type__token': payment.payment_type_token},
    ):
        if candidates.count() <= 1:
            break
        narrowed = candidates.filter(**narrower)
        if narrowed.exists():
            candidates = narrowed
    return candidates.first()


def change_commitment_payment_method(payment_id, payment_type_id, user,
                                     person_bank_id=None, company_bank_id=None):
    """Canvia la forma de pagament d'un rebut pendent d'un compromís i del seu termini.

    No genera moviments ni canvia l'estat del rebut: només el registra a l'historial.
    Retorna el rebut actualitzat.
    """
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(id=payment_id)
        check_commitment_payment_changeable(payment)

        payment_type = get_available_payment_types().filter(id=payment_type_id).first() if payment_type_id else None
        if not payment_type:
            raise CommitmentPaymentMethodError('invalid_payment_type')
        if payment_type.token == payment.payment_type_token:
            raise CommitmentPaymentMethodError('same_payment_type')

        contract = payment.commitment_deposit.contract
        person_bank = None
        payment_bank = None
        payment_swift = None

        if payment_type.token == 'DIRECT_DEBIT':
            person_banks = get_contract_person_banks(contract)
            if person_bank_id:
                person_bank = person_banks.filter(id=person_bank_id).first()
            elif contract and contract.payment and contract.payment.IBAN_id:
                person_bank = person_banks.filter(id=contract.payment.IBAN_id).first()
            if not person_bank:
                raise CommitmentPaymentMethodError('person_bank_required')
            payment_bank = person_bank.iban
            payment_swift = person_bank.swift
        elif payment_type.token == 'BANK_TRANSFER':
            # El compte on s'ha de pagar és un dels de l'empresa: mai un IBAN arribat a la petició.
            # Si l'empresa té comptes actius, n'és obligatori un.
            company_banks = get_contract_company_banks(contract)
            if company_bank_id or company_banks.exists():
                company_bank = company_banks.filter(id=company_bank_id).first() if company_bank_id else None
                if not company_bank:
                    raise CommitmentPaymentMethodError('company_bank_required')
                payment_bank = company_bank.iban
                payment_swift = company_bank.swift
        else:
            # Com en generar el rebut (`add_wallet_payment`): el compte de l'empresa del contracte, si n'hi ha
            company_bank = contract.payment.company_iban if contract and contract.payment else None
            if company_bank:
                payment_bank = company_bank.iban
                payment_swift = company_bank.swift

        previous_type = payment.payment_type
        previous_bank = payment.payment_bank
        was_marked = payment.is_marked_for_remittance
        # El termini es busca abans d'escriure, amb la forma de pagament que tenia el rebut
        guide = find_guide_commitment(payment)

        # `update()` perquè els senyals de pagament no generin moviments ni canvis d'estat
        Payment.objects.filter(id=payment.id).update(
            payment_type=payment_type.name,
            payment_type_token=payment_type.token,
            payment_bank=payment_bank,
            payment_swift=payment_swift,
            is_marked_for_remittance=False,
            updated_at=timezone.now(),
        )

        if guide:
            guide.payment_type = payment_type
            guide.payment_bank = person_bank
            guide.payment_bank_final = payment_bank
            guide.payment_swift_final = payment_swift
            guide.save(update_fields=['payment_type', 'payment_bank', 'payment_bank_final',
                                      'payment_swift_final', 'updated_at'])

        observation = f"Forma de pagament canviada: {previous_type or '-'} → {payment_type.name}"
        if (previous_bank or None) != (payment_bank or None):
            observation += f". Compte: {previous_bank or '-'} → {payment_bank or '-'}"
        if was_marked:
            observation += ". Tret de «marcat per remesar»"
        if not guide:
            observation += ". No s'ha trobat el termini del compromís"
        LogPaymentStatusChange.objects.create(
            object=payment,
            previous_status=payment.status,
            current_status=payment.status,
            used_payment_token=payment_type.token,
            observation=observation,
            user=user,
        )

    payment.refresh_from_db()
    # Perquè la pantalla avisi si el termini no s'ha pogut actualitzar
    payment.commitment_term_updated = guide is not None
    return payment
