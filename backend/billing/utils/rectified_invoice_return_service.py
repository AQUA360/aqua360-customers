"""Retorn bancari del cobrament d'una factura anul·lada i refeta.

Quan s'anul·la una factura cobrada retornant el cobrat al saldo, l'import entra al saldo de
l'abonat i la factura refeta el fa servir per pagar-se; la diferència hi queda com a saldo.
Si després el banc retorna aquell cobrament, aquells diners no han arribat mai: cal treure'ls
del saldo i, el que el saldo ja no pugui cobrir, deixar-ho pendent a la factura refeta, amb la
seva forma de pagament habitual. El saldo no queda mai en negatiu.
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from billing.models import Invoice, InvoiceStatus, Payment, PaymentStatus
from contract.models import PaymentType, PiggyBankMovement
from coredata.models import ConfigProject, PersonPiggyBankMovement
from coredata.utils.name_utils import generate_token

logger = logging.getLogger(__name__)

BALANCE_TOKEN = "BALANCE"
ZERO = Decimal('0.00')


def _config_value(token):
    return ConfigProject.objects.filter(token=token).values_list('value', flat=True).first()


def _balance_credit(payment):
    """Moviment de saldo que va generar l'anul·lació a partir del cobrament, i el model del moneder.

    L'anul·lació (amb el saldo retornat) deixa un moviment positiu lligat al cobrament original,
    al moneder del contracte o, si la factura era d'una sol·licitud sense contracte, al de la persona.
    """
    credit = PiggyBankMovement.objects.filter(payment=payment, is_positive=True, is_active=True).order_by('id').first()
    if credit:
        return credit, PiggyBankMovement, 'piggy_bank'
    credit = PersonPiggyBankMovement.objects.filter(payment=payment, is_positive=True, is_active=True).order_by('id').first()
    if credit:
        return credit, PersonPiggyBankMovement, 'person_piggy_bank'
    return None, None, None


def _already_reversed(payment, movement_model):
    return movement_model.objects.filter(payment=payment, is_positive=False, is_active=True).exists()


def refactored_invoice_of(invoice):
    """Factura refeta (la més recent i no anul·lada) d'una factura anul·lada."""
    if not invoice or not invoice.token:
        return None
    invoices = Invoice.objects.filter(refactored_token=invoice.token, is_active=True)
    invoice_type_token = _config_value('invoice_type_invoice_token')
    if invoice_type_token:
        invoices = invoices.filter(type__token=invoice_type_token)
    cancelled_token = _config_value('invoice_status_cancelled_token')
    if cancelled_token:
        invoices = invoices.exclude(status__token=cancelled_token)
    return invoices.exclude(return_token__gt='').order_by('-created_at', '-id').first()


def _balance_payments(invoice):
    """Pagaments de la factura cobrats amb saldo, del més recent al més antic."""
    if not invoice:
        return Payment.objects.none()
    paid_token = _config_value('payment_status_paid_token')
    return invoice.payments.filter(
        is_active=True, status__token=paid_token, payment_type_token=BALANCE_TOKEN,
    ).order_by('-id')


def refactored_unpaid_payment_ids(payments):
    """Pagaments pendents de cobrar de les factures refetes d'aquests pagaments (per reclamar-los)."""
    unpaid_tokens = [t for t in (
        _config_value('payment_status_pending_token'),
        _config_value('payment_status_expired_token'),
        _config_value('payment_status_returned_token'),
    ) if t]
    ids = []
    for payment in payments.select_related('invoice'):
        refactored_invoice = refactored_invoice_of(payment.invoice)
        if refactored_invoice:
            ids.extend(refactored_invoice.payments.filter(
                is_active=True, status__token__in=unpaid_tokens).values_list('id', flat=True))
    return ids


def _amount(value):
    return Decimal(str(value or 0)).quantize(Decimal('0.01'))


def rectified_return_plan(payment):
    """Què farà el retorn: saldo a treure, import que queda pendent a la factura refeta i el que no es cobreix.

    Retorna None si el cobrament no va generar saldo (o ja s'ha desfet).
    """
    credit, movement_model, piggy_field = _balance_credit(payment)
    if not credit or _already_reversed(payment, movement_model):
        return None
    piggy_bank = getattr(credit, piggy_field)
    credit_amount = _amount(credit.amount)
    available = max(_amount(piggy_bank.amount), ZERO)
    balance_to_remove = min(credit_amount, available)
    shortfall = credit_amount - balance_to_remove
    refactored_invoice = refactored_invoice_of(payment.invoice)
    paid_with_balance = sum((_amount(p.amount) for p in _balance_payments(refactored_invoice)), ZERO)
    refactored_debt = min(shortfall, paid_with_balance)
    return {
        'credit': credit,
        'movement_model': movement_model,
        'piggy_field': piggy_field,
        'piggy_bank': piggy_bank,
        'credit_amount': credit_amount,
        'balance_to_remove': balance_to_remove,
        'refactored_invoice': refactored_invoice,
        'refactored_debt': refactored_debt,
        'uncovered': shortfall - refactored_debt,
    }


def _usual_payment_method(invoice):
    """Forma de pagament habitual de la factura: la seva o, si s'havia pagat tota amb saldo, la del contracte."""
    if invoice.payment_type_token_final and invoice.payment_type_token_final not in (BALANCE_TOKEN, '-'):
        payment_type = PaymentType.objects.filter(token=invoice.payment_type_token_final).first()
        return payment_type, invoice.payment_bank_final, invoice.payment_swift_final
    contract = invoice.contract or (invoice.contract_termination.contract if invoice.contract_termination else None)
    contract_payment = contract.payment if contract else None
    if not contract_payment or not contract_payment.type:
        return None, None, None
    if contract_payment.company_iban:
        return contract_payment.type, contract_payment.company_iban.iban, contract_payment.company_iban.swift
    if contract_payment.IBAN:
        return contract_payment.type, contract_payment.IBAN.iban, contract_payment.IBAN.swift
    return contract_payment.type, None, None


def _new_payment(invoice, source, amount, status, payment_type_name, payment_type_token, bank=None, swift=None,
                 due_date=None, payment_date=None):
    from billing.utils.invoice_service import generate_payment_id
    return Payment.objects.create(
        token=generate_payment_id('01', exploitation_token=invoice.exploitation.token if invoice.exploitation else '0'),
        name=source.name or invoice.title_final,
        status=status,
        contract=source.contract,
        invoice=invoice,
        amount=amount,
        due_date=due_date or source.due_date,
        payment_type=payment_type_name,
        payment_type_token=payment_type_token,
        payment_date=payment_date,
        payment_bank=bank,
        payment_swift=swift,
        address_final=source.address_final,
        location_final=source.location_final,
        customer_final=source.customer_final,
        customer_token_final=source.customer_token_final,
        payer_final=source.payer_final,
        payer_token_final=source.payer_token_final,
    )


def _move_piggy(plan, amount, is_positive, payment, movement_date, user=None):
    """Moviment de saldo i actualització atòmica de l'import del moneder."""
    piggy_bank = plan['piggy_bank']
    delta = amount if is_positive else -amount
    type(piggy_bank).objects.filter(id=piggy_bank.id).update(amount=F('amount') + delta)
    plan['movement_model'].objects.create(**{
        'token': generate_token(plan['movement_model']),
        plan['piggy_field']: piggy_bank,
        'amount': amount,
        'is_positive': is_positive,
        'movement_date': movement_date,
        'payment': payment,
        'user': user,
    })


def _move_debt_to_refactored_invoice(plan, user, movement_date):
    """Deixa pendent a la factura refeta la part que s'havia pagat amb el saldo que ja no existeix.

    Els pagaments amb saldo afectats s'anul·len sencers (l'import torna al saldo); si en sobra
    una part, es torna a pagar amb saldo, i la resta queda en un pagament pendent amb la forma
    de pagament habitual. Retorna el pagament pendent.
    """
    from billing.utils.confirm_invoice_service import get_payment_status_token_for_invoice_status
    from billing.utils.payment_service import generate_payment_movement, log_invoice_status, log_payment_status

    invoice = plan['refactored_invoice']
    debt = plan['refactored_debt']
    paid_status = PaymentStatus.objects.get(token=_config_value('payment_status_paid_token'))
    cancelled_status = PaymentStatus.objects.get(token=_config_value('payment_status_cancelled_token'))
    balance_type = PaymentType.objects.filter(token=BALANCE_TOKEN).first()

    remaining = debt
    source = None
    for balance_payment in _balance_payments(invoice):
        if remaining <= 0:
            break
        source = source or balance_payment
        amount = _amount(balance_payment.amount)
        moved = min(amount, remaining)
        remaining -= moved
        # Torna al saldo el que s'havia consumit i anul·la el pagament
        _move_piggy(plan, amount, True, balance_payment, movement_date, user)
        log_payment_status(balance_payment, cancelled_status, user, movement_date, BALANCE_TOKEN)
        generate_payment_movement(balance_payment, cancelled_status, movement_date, BALANCE_TOKEN, None, user)
        balance_payment.status = cancelled_status
        balance_payment.save()
        kept = amount - moved
        if kept > 0:
            # La part que el saldo encara cobreix continua pagada amb saldo
            kept_payment = _new_payment(
                invoice, balance_payment, kept, PaymentStatus.objects.get(token=_config_value('payment_status_pending_token')),
                balance_type.name if balance_type else BALANCE_TOKEN, BALANCE_TOKEN, payment_date=movement_date)
            generate_payment_movement(kept_payment, paid_status, movement_date, BALANCE_TOKEN, None, user)
            kept_payment.status = paid_status
            kept_payment.paid_at = movement_date
            kept_payment.save()
            _move_piggy(plan, kept, False, kept_payment, movement_date, user)

    invoice_status = InvoiceStatus.objects.get(token=_config_value(
        'invoice_status_confirmed_token' if invoice.due_date and invoice.due_date > timezone.localdate()
        else 'invoice_status_expired_token'))
    payment_status = PaymentStatus.objects.get(token=get_payment_status_token_for_invoice_status(invoice_status.token))
    payment_type, bank, swift = _usual_payment_method(invoice)
    pending_payment = _new_payment(
        invoice, source, debt, payment_status,
        payment_type.name if payment_type else None, payment_type.token if payment_type else None,
        bank=bank, swift=swift, due_date=invoice.due_date or movement_date,
    )

    if invoice.status_id != invoice_status.id:
        log_invoice_status(invoice, invoice_status, user)
    invoice.status = invoice_status
    invoice.left_to_pay = _amount(invoice.left_to_pay) + debt
    if payment_type and invoice.payment_type_token_final == BALANCE_TOKEN:
        invoice.payment_type = payment_type
        invoice.payment_type_final = payment_type.name
        invoice.payment_type_token_final = payment_type.token
        invoice.payment_bank_final = bank
        invoice.payment_swift_final = swift
    invoice.save()
    return pending_payment


def reverse_rectified_payment_balance(payment, user, rejection_date, returned_status, reject_motive=None,
                                      payment_remittance=None, payment_bank=None):
    """Aplica el retorn bancari d'un cobrament d'una factura anul·lada i refeta.

    Treu del saldo l'import que el cobrament hi havia deixat; el que el saldo no cobreix queda
    pendent a la factura refeta. Deixa constància del retorn al cobrament original, que continua
    abonat. Els senyals de pagament han d'estar desconnectats. Retorna el pla aplicat (amb el
    pagament pendent creat, si n'hi ha) o None si no hi havia res a fer.
    """
    from billing.utils.payment_service import generate_payment_movement

    with transaction.atomic():
        plan = rectified_return_plan(payment)
        if not plan:
            return None
        # Bloqueja el moneder i torna a calcular amb l'import actual
        type(plan['piggy_bank']).objects.select_for_update().filter(id=plan['piggy_bank'].id).first()
        plan = rectified_return_plan(payment)
        if not plan:
            return None
        movement_date = rejection_date or timezone.localdate()

        plan['pending_payment'] = None
        if plan['refactored_debt'] > 0:
            plan['pending_payment'] = _move_debt_to_refactored_invoice(plan, user, movement_date)
        # El cobrament no ha arribat: es treu el saldo que havia generat, menys la part que ja s'havia
        # gastat fora de la factura refeta (no es pot treure sense deixar el saldo en negatiu)
        _move_piggy(plan, plan['credit_amount'] - plan['uncovered'], False, payment, movement_date, user)

        generate_payment_movement(
            payment, returned_status, movement_date, 'DIRECT_DEBIT',
            payment_bank or payment.payment_bank, user, reject_motive, payment_remittance)

        if plan['uncovered'] > 0:
            logger.warning(
                "Retorn d'una factura refeta: %s € del saldo ja s'havien gastat fora de la factura refeta (pagament %s)",
                plan['uncovered'], payment.id)
    return plan
