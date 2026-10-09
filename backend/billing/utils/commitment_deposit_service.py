from django.db import transaction
from decimal import Decimal
import uuid
from billing.models import CommitmentDeposit, CommitmentDepositStatus, Payment, PaymentCommitment, PaymentCommitmentStatus, PaymentStatus
from contract.models import PaymentType
from coredata.models import ConfigProject
from coredata.utils.name_utils import generate_token
from logger.models import LogCommitmentDepositMovement
from notification.models import Notification
from billing.utils.payment_service import log_payment_status, generate_payment_movement

def add_new_payment_deposit(payment, user, is_wallet=False, company_bank=None):
    print("1 - adding new payment to commitment deposit")
    deposit = payment.commitment_deposit
    if not deposit:
        return
    
    payment_commitment_paid = PaymentCommitmentStatus.objects.get(token=ConfigProject.objects.get(token='payment_commitment_status_paid_token').value)
    payment_commitment_partially_paid = PaymentCommitmentStatus.objects.get(token=ConfigProject.objects.get(token='payment_commitment_status_partially_paid_token').value)
    payment_commitment_pending = PaymentCommitmentStatus.objects.get(token=ConfigProject.objects.get(token='payment_commitment_status_pending_token').value)
    
    # Add confirmed status as valid for payment processing
    payment_commitment_confirmed = None
    try:
        confirmed_token = ConfigProject.objects.get(token='payment_commitment_status_confirmed_token').value
        payment_commitment_confirmed = PaymentCommitmentStatus.objects.filter(token=confirmed_token).first()
    except (ConfigProject.DoesNotExist, PaymentCommitmentStatus.DoesNotExist):
        pass
    
    commitment_deposit_paid = CommitmentDepositStatus.objects.get(token=ConfigProject.objects.get(token='commitment_deposit_status_paid_token').value)
    commitment_deposit_partially_paid = CommitmentDepositStatus.objects.get(token=ConfigProject.objects.get(token='commitment_deposit_status_partially_paid_token').value)
    commitment_deposit_cancelled = ConfigProject.objects.get(token='commitment_deposit_status_cancelled_token').value
    
    if deposit.status and deposit.status.token == commitment_deposit_cancelled:
        return
    
    log_data ={
        "object": deposit,
        "previous_remaining": deposit.remaining,
        "current_remaining": deposit.remaining - payment.currently_paid,
        "user": user,
        "new_payment": payment,
    }
    
    log = LogCommitmentDepositMovement.objects.create(**log_data)
    
    deposit.remaining -= payment.currently_paid
    deposit.remaining_to_share += payment.currently_paid
    
    if deposit.remaining <= 0:
        deposit.status = commitment_deposit_paid
        log.current_status = commitment_deposit_paid
        if deposit.remaining < 0:
            notification_save = {
                'token': uuid.uuid4(),
                'name': f"Compromís de pagament excedit",
                'description': f"Compromís de pagament amb pagament excedit. Total excedit: {abs(deposit.remaining)}",
                'module': 'billing',
                'entity': 'commitment-deposits',
                'object_id': deposit.id,
                'is_active': True
            }
            notification = Notification.objects.create(**notification_save)
    else:
        if deposit.status.token != commitment_deposit_paid.token:
            deposit.status = commitment_deposit_partially_paid
            log.current_status = commitment_deposit_partially_paid
    
    deposit.save()
    #log.save()
    if not is_wallet:
        add_wallet_payment(payment, user, True, company_bank=company_bank) 
    
    
    payments_currency = payment.currently_paid
    
    valid_commitment_statuses = [payment_commitment_partially_paid, payment_commitment_pending]
    # IF CONFIRMED DO NOT PAY, ALREADY RELATED TO EXITING PAYMENT AND MONEY COULD COME FROM SOMEWHERE ELSE
    if payment_commitment_confirmed and is_wallet:
        valid_commitment_statuses.append(payment_commitment_confirmed)
        
    deposit_guide_payments = PaymentCommitment.objects.filter(commitment_deposit=deposit, is_guide=True, status__in=valid_commitment_statuses).order_by('due_date').distinct()
    
    for com_payment in deposit_guide_payments:
        left_to_pay = float(com_payment.amount) - float(com_payment.currently_paid)

        if left_to_pay > payments_currency and round(payments_currency, 3) > 0:
            com_payment.currently_paid += payments_currency
            com_payment.status = payment_commitment_partially_paid
            com_payment.save()
            payments_currency = 0
        else:
            com_payment.currently_paid = com_payment.amount
            #com_payment.status = payment_commitment_paid
            com_payment.save()
            payments_currency -= Decimal(float(left_to_pay))
        
        if com_payment.currently_paid == com_payment.amount:
            com_payment.status = payment_commitment_paid
            com_payment.save()
        else:
            if payments_currency > 0:
                com_payment.status = payment_commitment_partially_paid
        
        if round(payments_currency, 3) <= 0:
            break
    
    payment_status_paid = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)
    payments_invoices = Payment.objects.filter(invoice__in=deposit.invoices.all()).exclude(status=payment_status_paid)
    usable_remaining = False
    counter = 0
    while not usable_remaining and counter < len(payments_invoices):
        payment = payments_invoices[counter]
        if payment.amount <= deposit.remaining_to_share:
            usable_remaining = True
            notification_save = {
            'token': uuid.uuid4(),
            'name': f"Pagament liquidable",
            'description': f"Compromís de pagament {deposit.token} amb pagaments de factura liquidables",
            'module': 'billing',
            'entity': 'commitment-deposits',
            'object_id': deposit.id,
            'is_active': True
            }
            Notification.objects.create(**notification_save)
            
        counter += 1
    
    


def add_wallet_payment(commitment_payment, user, is_paid, wallet_payment_date=None, company_bank=None):
    print("2 - adding new payment to commitment deposit")
    print("is paid: ", is_paid)
    payment_paid = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)
    payment_pending = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_pending_token').value)
    
    with transaction.atomic():
        # Lock the commitment deposit to avoid collisions in token generation
        deposit = CommitmentDeposit.objects.select_for_update().get(id=commitment_payment.commitment_deposit.id)
        
        prefix_token = deposit.token
        existing_tokens = Payment.objects.filter(token__startswith=prefix_token).values_list('token', flat=True)
        max_suffix = 0
        for existing_token in existing_tokens:
            if existing_token.startswith(prefix_token):
                suffix = existing_token[len(prefix_token):]
                if suffix.isdigit():
                    max_suffix = max(max_suffix, int(suffix))
        
        next_suffix = max_suffix + 1
            
        # Check for existence and increment if necessary to avoid IntegrityError
        while Payment.objects.filter(token=f"{prefix_token}{next_suffix:02d}").exists():
            next_suffix += 1

        bank_payment_token = ConfigProject.objects.get(token='bank_payment_token').value
        
        comp_bank = company_bank or (deposit.contract.payment.company_iban if deposit.contract and deposit.contract.payment and deposit.contract.payment.company_iban else None)
        payment_bank_val = comp_bank.iban if comp_bank else commitment_payment.payment_bank_final
        payment_swift_val = comp_bank.swift if comp_bank else commitment_payment.payment_swift_final

        payment_data = {
            #"token": generate_token(Payment),
            "token": f"{prefix_token}{next_suffix:02d}",
            "name": f"COMPROMÍS DE PAGAMENT {deposit.token}",
            "status": payment_paid if is_paid else payment_pending,
            "contract": deposit.contract,
            "customer_final": deposit.customer_final,
            "customer_token_final": deposit.customer_token_final,
            "payer_final": f"{deposit.contract.payment.IBAN.person.name} {deposit.contract.payment.IBAN.person.surname}" if deposit.contract.payment and deposit.contract.payment.IBAN and deposit.contract.payment.IBAN.person else f"{deposit.contract.holder.name} {deposit.contract.holder.surname}" if deposit.contract.holder else deposit.customer_final,
            "payer_token_final": deposit.contract.payment.IBAN.person.token if deposit.contract.payment and deposit.contract.payment.IBAN and deposit.contract.payment.IBAN.person else deposit.contract.holder.token if deposit.contract.holder else deposit.customer_token_final,
            "commitment_deposit": deposit,
            "amount": commitment_payment.amount if commitment_payment.is_guide else commitment_payment.currently_paid,
            "payment_type": commitment_payment.payment_type.name,
            "payment_type_token": commitment_payment.payment_type.token,
            "payment_bank": payment_bank_val,
            "payment_swift": payment_swift_val,
            "address_final": deposit.address_final,
            "location_final": deposit.location_final,
            "payment_date": wallet_payment_date if wallet_payment_date else commitment_payment.payment_date,
            "due_date": commitment_payment.due_date if commitment_payment.is_guide else commitment_payment.payment_date,
        }
        print("payment data: ", payment_data)
        payment = Payment.objects.create(**payment_data)
        if is_paid:
            payment.status = payment_pending
            log_payment_status(
                payment,
                payment_paid,
                user,
                payment.payment_date
            )
            generate_payment_movement(
                payment,
                payment_paid,
                payment.payment_date,
                payment.payment_type_token,
                payment.payment_bank,
                user,
                None,
                payment.remittances.filter(sent_at__isnull=False).order_by('-sent_at').first()
            )
            payment.status = payment_paid

        if commitment_payment.payment_type.token == bank_payment_token:
            from billing.utils.payment_pdf_service import generate_report_payment_pdf
            
            document, _ = generate_report_payment_pdf(payment)
            payment.document = document
            payment._skip_signal = True
            payment.save()
        print("after creating payment")
        return payment
        
    
def wallet_payment_deposit_update(payment, user, request):
    from billing.serializers.payment_commitment_serializer import PaymentCommitmentSaveSerializer
    
    status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)
    
    commitment_deposit = payment.commitment_deposit
    """ payment._skip_signal = True
    #log_payment_status(payment, status, user)
    payment.status = status
    payment.save() """
    
    payment_type = PaymentType.objects.filter(token=payment.payment_type_token).first()
    total_payments = PaymentCommitment.objects.filter(commitment_deposit=commitment_deposit, is_guide=False).count()
    
    payment_data = {
        #"token": generate_token(PaymentCommitment),
        "token": f"{commitment_deposit.token}{total_payments}",
        "commitment_deposit_id": commitment_deposit.id,
        "payment_type_id": payment_type.id,
        "currently_paid": payment.amount,
        "payment_date": payment.payment_date,
        "is_guide": False,
        "is_wallet": True,
    }
    
    PaymentCommitmentSaveSerializer(commitment_deposit, context={'request': request}).create(payment_data)
    
def update_deposit(invoice_payment):
    status_paid = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)
    if invoice_payment.status != status_paid:
        return
    
    status_cancelled_token = ConfigProject.objects.get(token='commitment_deposit_status_cancelled_token').value
    commitment_deposits = CommitmentDeposit.objects.filter(invoices=invoice_payment.invoice).exclude(status__token=status_cancelled_token)
    paid_status = CommitmentDepositStatus.objects.get(token=ConfigProject.objects.get(token='commitment_deposit_status_paid_token').value)
    partially_paid_status = CommitmentDepositStatus.objects.get(token=ConfigProject.objects.get(token='commitment_deposit_status_partially_paid_token').value)
    if commitment_deposits.exists():
        for deposit in commitment_deposits:
            if deposit.remaining == 0 and deposit.remaining_to_share == 0:
                deposit.status = paid_status
            else:
                if deposit.status.token != paid_status.token:
                    deposit.status = partially_paid_status
            #deposit.remaining_to_share -= invoice_payment.amount
            deposit.save()