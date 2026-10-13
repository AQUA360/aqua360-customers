import datetime
from billing.models import Invoice, Payment, PaymentStatus
from contract.models import Bail, BailStatus, PiggyBankMovement
from coredata.models import ConfigProject
from django.utils import timezone
from coredata.utils.name_utils import generate_token
from logger.models import LogBailStatus
from billing.utils.invoice_service import generate_payment_id, invoice_generate_return_bail

def pending_bail_contract_termination(user, instance):
    if instance.payment:
        bail_unreturned_token = ConfigProject.objects.get(token='bail_status_unreturned_token').value
        bails = Bail.objects.filter(contract=instance, status__token=bail_unreturned_token)
        
        payment_bank = instance.payment.IBAN.id if instance.payment.IBAN else None
        
        if bails.count() > 0:
            invoice = invoice_generate_return_bail(user, instance.id, 'RETORN FIANÇA', instance.payment.type.id, payment_bank, True)
            pending_bail_token = ConfigProject.objects.get(token='bail_status_pending_token').value
            for bail in bails:
                prev_status = bail.status
                
                bail.status = BailStatus.objects.get(token=pending_bail_token)
                bail.invoice = invoice
                
                #TODO: GENERATE AND SET INVOICE
                bail.save()
                
                LogBailStatus.objects.create(
                    object = bail,
                    previous_status = prev_status,
                    current_status = bail.status,
                    user = user,
                    timestamp = datetime.datetime.now(),
                    observation = None
                )
    
    

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
        
        