import datetime
from billing.models import Invoice, InvoiceStatus, Payment, PaymentStatus
from billing.utils.confirm_invoice_service import confirm_invoice
from billing.utils.payment_service import generate_payment_movement, log_payment_status
from contract.models import Bail, BailStatus, Contract, PaymentType, PiggyBankMovement
from coredata.models import ConfigProject
from django.db import transaction
from django.utils import timezone
from coredata.utils.name_utils import generate_token
from logger.models import LogBailStatus
from billing.utils.invoice_service import generate_payment_id, invoice_generate_return_bail

BAIL_RETURN_INVOICE_DISABLED_TOKEN = 'BAIL_RETURN_INVOICE_DISABLED'


def is_bail_return_invoice_disabled():
    """
    Retorna si s'ha de saltar la factura de retorn de fiança, segons el
    ConfigProject amb token `BAIL_RETURN_INVOICE_DISABLED`. Si és 'true', el
    retorn de fiances es completa igualment (estat retornat) però sense generar
    cap factura ni abonar l'import al saldo. Deshabilitat per defecte.
    """
    config = ConfigProject.objects.filter(token=BAIL_RETURN_INVOICE_DISABLED_TOKEN).first()
    if not config or not config.value:
        return False
    return config.value.lower() == 'true'


def liquidate_bail(user, bails, balance_contract=None):
    bail_status_returned_token = ConfigProject.objects.get(token='bail_status_returned_token').value
    returned_status = BailStatus.objects.get(token=bail_status_returned_token)
    status_invoice_confirmed = InvoiceStatus.objects.get(
        token=ConfigProject.objects.get(token='invoice_status_confirmed_token').value
    )
    payment_status_piggy = PaymentStatus.objects.get(
        token=ConfigProject.objects.get(token='payment_status_piggy_token').value
    )
    processed_invoice_ids = set()
    skip_invoice = is_bail_return_invoice_disabled()

    for bail in bails:
        prev_status = bail.status
        bail.status = returned_status
        bail.return_date = timezone.now()
        bail.payment_date = timezone.now()
        bail.save()

        LogBailStatus.objects.create(
            object=bail,
            previous_status=prev_status,
            current_status=bail.status,
            user=user,
            timestamp=timezone.now(),
            observation=None,
        )

        invoice = bail.invoice
        if invoice and invoice.id not in processed_invoice_ids:
            processed_invoice_ids.add(invoice.id)
            invoice.status = status_invoice_confirmed
            invoice.save()
            confirm_invoice(invoice)

            invoice_payments = Payment.objects.filter(invoice=invoice)
            for payment in invoice_payments:
                log_payment_status(payment, payment_status_piggy, user)
                generate_payment_movement(
                    payment, payment_status_piggy,
                    payment.payment_date, "BALANCE",
                    None, user,
                    None,
                    None,
                )
                payment.status = payment_status_piggy
                payment.save()
                payment.refresh_from_db()

        # Sense factura de retorn no s'abona res al saldo (del contracte ni de la persona).
        if skip_invoice and not invoice:
            continue

        # Termination credits bail.contract. An immediate return of one bail credits
        # the contract that lists it in Contract.bails.
        contract = balance_contract or bail.contract
        if not contract or not contract.piggy_bank:
            raise Exception("Contract balance not found")

        PiggyBankMovement.objects.create(
            token=generate_token(PiggyBankMovement),
            piggy_bank=contract.piggy_bank,
            amount=bail.amount,
            is_positive=True,
            movement_date=timezone.now(),
            bail=bail,
        )
        contract.piggy_bank.amount += bail.amount
        contract.piggy_bank.save()


def pending_bail_contract_termination(user, instance):
    skip_invoice = is_bail_return_invoice_disabled()
    if instance.payment or skip_invoice:
        bail_unreturned_token = ConfigProject.objects.get(token='bail_status_unreturned_token').value
        bails = Bail.objects.filter(contract=instance, status__token=bail_unreturned_token)
        
        if bails.count() > 0:
            invoice = None
            if not skip_invoice:
                payment_bank = instance.payment.IBAN.id if instance.payment.IBAN else None
                invoice = invoice_generate_return_bail(user, instance.id, 'RETORN FIANÇA', instance.payment.type.id, payment_bank, True)
            pending_bail_token = ConfigProject.objects.get(token='bail_status_pending_token').value
            pending_bails = []
            for bail in bails:
                prev_status = bail.status
                
                bail.status = BailStatus.objects.get(token=pending_bail_token)
                bail.invoice = invoice
                
                bail.save()
                
                LogBailStatus.objects.create(
                    object = bail,
                    previous_status = prev_status,
                    current_status = bail.status,
                    user = user,
                    timestamp = datetime.datetime.now(),
                    observation = None
                )
                pending_bails.append(bail)

            liquidate_bail(user, pending_bails)
    
    

def immediate_return_bail(user, bail_id):
    """Return one unreturned bail the same way a contract termination does.

    The contract is the one that includes this bail in Contract.bails, not Bail.contract.
    Unreturned becomes pending with a pre-invoice, then returned, and the bail amount
    is added to that contract's balance. With BAIL_RETURN_INVOICE_DISABLED enabled,
    no invoice is generated and no balance is credited.
    """
    with transaction.atomic():
        bail = Bail.objects.select_for_update().get(id=bail_id)
        unreturned_token = ConfigProject.objects.get(token='bail_status_unreturned_token').value
        if not bail.status or bail.status.token != unreturned_token:
            raise ValueError("Bail is not unreturned")

        contract = (
            Contract.objects.filter(bails=bail)
            .select_related('payment', 'payment__IBAN', 'payment__type', 'piggy_bank')
            .order_by('id')
            .first()
        )
        if not contract:
            raise ValueError("Contract not found for this bail")
        skip_invoice = is_bail_return_invoice_disabled()
        if not contract.piggy_bank and not skip_invoice:
            raise ValueError("Contract balance not found")

        invoice = None
        if not skip_invoice:
            payment_type_id = contract.payment.type_id if contract.payment else None
            if not payment_type_id:
                default_payment_type = PaymentType.objects.filter(is_default=True).first()
                if not default_payment_type:
                    raise ValueError("Contract has no payment method")
                payment_type_id = default_payment_type.id

            payment_bank = contract.payment.IBAN.id if contract.payment and contract.payment.IBAN else None
            invoice = invoice_generate_return_bail(
                user,
                contract.id,
                'RETORN FIANÇA',
                payment_type_id,
                payment_bank,
                True,
                bails=[bail],
            )
            if not invoice:
                raise ValueError("Could not generate return invoice")

        prev_status = bail.status
        pending_status = BailStatus.objects.get(
            token=ConfigProject.objects.get(token='bail_status_pending_token').value
        )
        bail.status = pending_status
        bail.invoice = invoice
        bail.save()

        LogBailStatus.objects.create(
            object=bail,
            previous_status=prev_status,
            current_status=bail.status,
            user=user,
            timestamp=timezone.now(),
            observation=None,
        )

        liquidate_bail(user, [bail], balance_contract=contract)
        bail.refresh_from_db()
        return bail


def return_bail(user, bail_id):
    bail = Bail.objects.get(id= bail_id)
    prev_status = bail.status
    bail_status_returned_token = ConfigProject.objects.get(token='bail_status_returned_token').value
    bail.return_date = datetime.datetime.now().date()
    bail.status = BailStatus.objects.get(token=bail_status_returned_token)
    bail.save()

    LogBailStatus.objects.create(
                object = bail,
                previous_status = prev_status,
                current_status = bail.status,
                user = user,
                timestamp = datetime.datetime.now(),
                observation = None
            )
    return bail

def check_unpaid_invoices(contracts):
    try:
        for contract in contracts:
            unpaid_token = ConfigProject.objects.get(token='invoice_status_expired_token').value
            status_payment_paid = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)
            payment_status_irrecoverable = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_irrecoverable_token').value)
            invoices = Invoice.objects.filter(contract=contract, status__token=unpaid_token)
            piggy_amount = contract.piggy_bank.amount
            for invoice in invoices:
                payments = Payment.objects.filter(invoice=invoice)
                if invoice.left_to_pay > 0 and invoice.left_to_pay < piggy_amount:
                    for payment in payments:
                        payment.status = status_payment_paid
                        payment.save()
                        piggy_amount -= payment.amount
                        contract.piggy_bank.amount = piggy_amount
                        contract.piggy_bank.save()
                        PiggyBankMovement.objects.create(
                            token=generate_token(PiggyBankMovement),
                            piggy_bank=contract.piggy_bank,
                            amount=payment.amount,
                            is_positive=False,
                            movement_date=datetime.datetime.now(),
                            payment=payment,
                        )
                else:
                    for payment in payments:
                        payment.status = payment_status_irrecoverable
                        payment.save()
                        
            #COMMENTED SINCE ITS USE IS WEIRD (FOR NOW)
            """ if piggy_amount > 0:
                if contract.payment and contract.payment.IBAN and contract.payment.IBAN.person:
                    payer_final = f"{contract.payment.IBAN.person.name} {contract.payment.IBAN.person.surname}"
                    payer_token_final = contract.payment.IBAN.person.token
                else:
                    payer_final = f"{contract.holder.name} {contract.holder.surname}"
                    payer_token_final = contract.holder.token
                new_payment = Payment.objects.create(
                    token=generate_payment_id('01'),
                    name=f"APROPIACIÓ SALDO {contract.token}",
                    status=status_payment_paid,
                    contract=contract,
                    due_date=timezone.now(),
                    amount=float(piggy_amount),
                    payment_date=timezone.now(),
                    customer_final=f"{contract.holder.name} {contract.holder.surname}" if contract else f"{contract.piggy_bank.person.name} {contract.piggy_bank.person.surname}",
                    customer_token_final=contract.holder.token if contract else contract.piggy_bank.person.token,
                    payer_final=payer_final,
                    payer_token_final=payer_token_final,
                )
                contract.piggy_bank.amount = 0
                contract.piggy_bank.save()
                PiggyBankMovement.objects.create(
                    token=generate_token(PiggyBankMovement),
                    piggy_bank=contract.piggy_bank,
                    amount=piggy_amount,
                    is_positive=False,
                    movement_date=datetime.datetime.now(),
                    payment=new_payment,
                ) """
        
        
    except Exception as e:
        raise Exception(e)
        
        