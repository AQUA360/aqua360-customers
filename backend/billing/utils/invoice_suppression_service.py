import time

from django.utils import timezone
from django.utils.translation import gettext as _

from billing.models import InvoiceStatus, Payment, PaymentStatus, PaymentType
from billing.utils.invoice_service import change_status_logger, generate_payment_id, return_invoice
from billing.utils.payment_service import disconnect_payment_signals, generate_payment_movement, log_payment_status, reconnect_payment_signals
from contract.models import PiggyBankMovement
from coredata.models import ConfigProject, PersonPiggyBankMovement
from coredata.utils.name_utils import generate_token


def invoice_needs_return(invoice):
    """
    Una factura emesa (amb número de sèrie legal) no es pot anul·lar sense el seu
    abonament (FR). Les prefactures i els pressupostos no tenen número legal, i les
    factures que ja tenen abonament (return_token) o que són elles mateixes un
    abonament no en necessiten cap més.
    """
    invoice_type_token = ConfigProject.objects.get(token='invoice_type_invoice_token').value
    pending_status_token = ConfigProject.objects.get(token='invoice_status_pending_token').value
    payoff_status_token = ConfigProject.objects.get(token='invoice_status_payoff_token').value
    if not invoice.type or invoice.type.token != invoice_type_token:
        return False
    if invoice.status and invoice.status.token in [pending_status_token, payoff_status_token]:
        return False
    if invoice.is_suppressed or invoice.return_token:
        return False
    return True


def suppress_invoice(invoice, user, reason=None, payment_type_id=None, return_paid_total=False,
                     return_paid_total_balance=False, return_paid_total_balance_type=None,
                     return_paid_total_balance_type_iban=None, target_status=None):
    """
    Anul·la una factura emesa generant-ne l'abonament (FR).

    L'estat final és Abonada (-6) si la factura té pagaments amb moviments i Anul·lada (-7)
    si no; target_status permet triar Abonada en una factura sense cobrar, però una factura
    que ha cobrat alguna cosa no pot quedar mai com a Anul·lada.
    Retorna l'abonament creat.
    """
    cancel_status = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_cancelled_token').value)
    dropped_status = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_dropped_token').value)
    payment_cancel = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_cancelled_token').value)
    payment_dropped = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_dropped_token').value)
    payment_pending = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_pending_token').value)
    payment_payoff = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_payoff_token').value)
    payment_paid_token = ConfigProject.objects.get(token='payment_status_paid_token').value
    payment_paid = PaymentStatus.objects.get(token=payment_paid_token)
    payment_returned = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_returned_token').value)

    has_movements = invoice.payments.filter(movements__gt=0).exists()
    if has_movements or (target_status is not None and target_status == cancel_status):
        invoice_status_to_change = cancel_status
        payment_status_to_change = payment_cancel
    else:
        invoice_status_to_change = dropped_status
        payment_status_to_change = payment_dropped

    disconnect_payment_signals()
    total_balance_returned = 0
    returned_payments = []
    try:
        contract = None
        if invoice.contract:
            contract = invoice.contract
        elif invoice.contract_termination:
            contract = invoice.contract_termination.contract
        # CONTRACT REQUEST NOW WORKS WITH PERSON PIGGY BANK

        if contract and contract.piggy_bank:
            piggy_bank = contract.piggy_bank
            payments = invoice.payments.filter(
                status__token=payment_paid_token,
            )
            for payment in payments:
                if return_paid_total or payment.payment_type_token == "BALANCE":
                    PiggyBankMovement.objects.create(
                        token=generate_token(PiggyBankMovement),
                        piggy_bank=piggy_bank,
                        amount=payment.amount,
                        is_positive=True,
                        movement_date=timezone.now(),
                        payment=payment,
                    )
                    piggy_bank.amount += payment.amount
                    total_balance_returned += payment.amount
                    returned_payments.append(payment.id)
                    if return_paid_total_balance:
                        try:
                            payment_type = PaymentType.objects.get(id=return_paid_total_balance_type)
                        except Exception as e:
                            payment_type = PaymentType.objects.get(token=payment.payment_type_token)
                        piggy_bank.amount -= payment.amount
                        new_return_payment = Payment.objects.create(
                            token=generate_payment_id('04'),
                            name=f"{_('RETURN BALANCE')} {contract.token}",
                            status=payment_pending if payment_type.token == "BANK_TRANSFER" else payment_paid,
                            contract=contract,
                            amount=float(payment.amount),
                            due_date=timezone.now(),
                            payment_type=payment_type.name,
                            payment_type_token=payment_type.token,
                            payment_date=timezone.now(),
                            payment_bank=return_paid_total_balance_type_iban['iban'] if payment_type.token == "BANK_TRANSFER" and return_paid_total_balance_type_iban else None,
                            payment_swift=return_paid_total_balance_type_iban['swift'] if payment_type.token == "BANK_TRANSFER" and return_paid_total_balance_type_iban else None,
                            customer_final=payment.customer_final,
                            customer_token_final=payment.customer_token_final,
                            payer_final=payment.payer_final,
                            payer_token_final=payment.payer_token_final,
                            address_final=payment.address_final,
                            location_final=payment.location_final,
                        )
                        new_return_payment.status = payment_pending
                        if payment_type.token != "BANK_TRANSFER":
                            generate_payment_movement(
                                new_return_payment,
                                payment_paid,
                                timezone.now(),
                                payment_type.token,
                                payment.payment_bank,
                                user,
                                add_bank=True,
                            )
                        PiggyBankMovement.objects.create(
                            token=generate_token(PiggyBankMovement),
                            piggy_bank=piggy_bank,
                            amount=payment.amount,
                            is_positive=False,
                            movement_date=timezone.now(),
                            payment=new_return_payment,
                        )
                else:
                    print("payment status: ", payment.status.name)
                    generate_payment_movement(
                        payment,
                        payment_returned,
                        timezone.now(),
                        payment.payment_type_token,
                        payment.payment_bank,
                        user,
                        add_bank=True,
                    )

            if total_balance_returned > 0:
                piggy_bank.save()
        elif invoice.connection_request or invoice.contract_request:
            person = invoice.connection_request.person if invoice.connection_request else invoice.contract_request.person if invoice.contract_request else None
            if person and person.piggy_bank:
                piggy_bank = person.piggy_bank
                payments = invoice.payments.filter(
                    status__token=payment_paid_token,
                )
                for payment in payments:
                    if return_paid_total or payment.payment_type_token == "BALANCE":
                        PersonPiggyBankMovement.objects.create(
                            token=generate_token(PersonPiggyBankMovement),
                            person_piggy_bank=piggy_bank,
                            amount=payment.amount,
                            is_positive=True,
                            movement_date=timezone.now(),
                            payment=payment,
                        )
                        piggy_bank.amount += payment.amount
                        total_balance_returned += payment.amount
                        returned_payments.append(payment.id)
                if total_balance_returned > 0:
                    piggy_bank.save()
    except Exception as e:
        print(e)
    print("returned payments: ", returned_payments)
    change_status_logger(user, invoice, invoice_status_to_change)

    movement_date = timezone.now()
    for payment in invoice.payments.all():
        log_payment_status(payment, payment_status_to_change, user)

    invoice.left_to_pay = invoice.total_final
    invoice.suppression_reason = reason
    invoice.suppressed_by = user
    invoice.suppressed_at = timezone.now()
    invoice.status = invoice_status_to_change
    invoice.payments.update(status=payment_status_to_change)
    invoice.save()
    reconnect_payment_signals()
    new_invoice = return_invoice(invoice, payment_type_id)

    # wait for sql refresh before generating payment movement
    print("total_balance_returned: ", total_balance_returned)
    if total_balance_returned > 0:
        try:
            time.sleep(1)
            return_payment = new_invoice.payments.first()
            return_payment.status = payment_pending

            generate_payment_movement(
                        return_payment, payment_payoff, movement_date,
                        "BALANCE",
                        None, user,
                        None, None
                    )
        except Exception as e:
            print(e)

    return new_invoice
