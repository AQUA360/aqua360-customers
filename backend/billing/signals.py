from decouple import config
from billing.views.invoice_pdf_view import generate_report_invoice_pdf
from django.db.models.signals import post_save, pre_save, pre_delete
from django.dispatch import receiver
from django.utils import translation
from django.utils.translation import gettext as _
from datetime import datetime
from django.utils import timezone
from dateutil.relativedelta import relativedelta
import datetime
import calendar
from faker import Faker
from requests import Request
from billing.models import CommitmentDeposit, EstimatedBag, EstimatedBagMovement, Invoice, InvoiceLog, InvoiceSerie, InvoiceStatus, InvoiceType, Payment, PaymentCommitment, PaymentCommitmentStatus, PaymentStatus, Reading
from billing.utils.commitment_deposit_service import update_deposit, wallet_payment_deposit_update
from billing.utils.payment_service import *
from claimrequest.models import ClaimRequest, ClaimRequestPayment, VulnerabilityRequest, VulnerabilityRequestStatus
from contract.models import Bail, BailStatus, Contract, PaymentType, PiggyBank, PiggyBankMovement
from notification.models import Notification
from contract.middleware import get_current_user
from coredata.utils.validators_utils import validate_nif
from logger.models import LogBailStatus, LogClaimRequestContractChange, LogCommitmentDepositMovement
from billing.utils.invoice_service import change_status_logger, check_piggy_bank, generate_serie_final, get_invoice_status, invoice_claim_paid_generate, invoice_return_charge
from verifactu.utils.save_verifactu_info import create_verifactu_invoice
import uuid

@receiver(pre_save, sender=Invoice)
def invoice_pre_save(sender, instance, **kwargs):
    if instance.pk:  # This is an update
        try:
            old_instance = Invoice.objects.get(pk=instance.pk)
            current_user = get_current_user()
            
            # Only proceed if we have a real user (not AnonymousUser)
            if current_user and not current_user.is_anonymous:
                operation_token = str(uuid.uuid4())
                
                fields = [f.name for f in Invoice._meta.fields]
                
                for field in fields:
                    old_value = getattr(old_instance, field)
                    new_value = getattr(instance, field)
                    
                    if old_value != new_value:
                        old_value_str = str(old_value) if old_value is not None else None
                        new_value_str = str(new_value) if new_value is not None else None
                        
                        InvoiceLog.objects.create(
                            invoice=instance,
                            field_name=field,
                            old_value=old_value_str,
                            new_value=new_value_str,
                            operation_token=operation_token,
                            user=current_user
                        )
        except Invoice.DoesNotExist:
            pass


@receiver(post_save, sender=Invoice)
def create_payment_invoice(sender, instance, created, **kwargs):
    if created:
        try:
            current_user = get_current_user()
            
            operation_token = str(uuid.uuid4())
            InvoiceLog.objects.create(
                invoice=instance,
                field_name='Created',
                new_value='True',
                operation_token=operation_token,
                user=current_user
            )
        except:
            pass
    
    # # No executar durant la càrrega de fixtures
    # if kwargs.get('raw', False):
    #     return
    
    # if not instance.id or hasattr(instance, '_skip_signal') or hasattr(instance, '_skip_signal_updating_verifactu'):
    #     return
    
    # # Check if invoice has line items
    # if instance.line_items.count() == 0:
    #     instance.refresh_from_db()
        
    
    # # Batch load all ConfigProject values at once to reduce queries
    # config_tokens = [
    #     'invoice_status_confirmed_token',
    #     'status_payoff',
    #     'invoice_status_cancelled_token',
    #     'invoice_status_pending_token',
    #     'invoice_status_paid_token',
    #     'direct_debit_token',
    #     'payment_status_pending_token',
    #     'payment_status_paid_token',
    #     'payment_status_cancelled_token',
    #     'token_general_invoice_serie',
    #     'token_ordinary_invoice_serie',
    #     'token_returned_invoice_serie',
    #     'token_refactored_invoice_serie',
    #     'invoice_type_invoice_token',
    #     'invoice_status_payoff_token',
    #     'payment_status_payoff_token'
    # ]
    # config_values = {
    #     cfg.token: cfg.value 
    #     for cfg in ConfigProject.objects.filter(token__in=config_tokens)
    # }
    
    # # Get status objects
    # status_confirmed = InvoiceStatus.objects.get(token=config_values['invoice_status_confirmed_token'])
    # status_payoff = InvoiceStatus.objects.get(token=config_values['invoice_status_payoff_token'])
    # status_cancelled = InvoiceStatus.objects.get(token=config_values['invoice_status_cancelled_token'])
    # status_pending_token = config_values['invoice_status_pending_token']
    # status_paid = InvoiceStatus.objects.get(token=config_values['invoice_status_paid_token'])
    # direct_debit_token = config_values['direct_debit_token']
    # payment_status_pending = PaymentStatus.objects.get(token=config_values['payment_status_pending_token'])
    # payment_status_payoff = PaymentStatus.objects.get(token=config_values['payment_status_payoff_token'])
    # payment_status_paid = PaymentStatus.objects.get(token=config_values['payment_status_paid_token'])
    # payment_balance = PaymentType.objects.get(token="BALANCE")

    # # Handle confirmed status
    # if instance.status == status_confirmed or instance.status == status_payoff:
    #     genPdf = not hasattr(instance, '_skip_pdf_generation')
        
    #     # Delete existing payment if any
    #     Payment.objects.filter(invoice=instance).delete()
        
    #     # Calculate dates
    #     remittance_date = _get_remittance_date(instance)
    #     base_date = _parse_date(instance.due_date)
    #     base_send_at = _parse_date(instance.send_at)
    #     if not instance.due_date:
    #         base_date = base_date + relativedelta(months=1)
        
    #     # Calculate payment date based on remittance date
    #     payment_date = base_date
    #     due_date = None
    #     send_at = None
    #     if remittance_date:
    #         # Get the last day of the base_date month using calendar.monthrange
    #         last_day_of_month = calendar.monthrange(base_date.year, base_date.month)[1]
    #         last_day_of_month_send = calendar.monthrange(base_send_at.year, base_send_at.month)[1]
    #         remittance_day = min(remittance_date, last_day_of_month)
    #         remittance_day_send = min(remittance_date, last_day_of_month_send)
    #         if remittance_day > base_date.day:
    #             payment_date = datetime.date(base_date.year, base_date.month, remittance_day)
    #             due_date = payment_date
    #         if base_send_at and base_send_at.day < remittance_day_send:
    #             send_at = datetime.date(base_send_at.year, base_send_at.month, remittance_day_send)
        
    #     # Check piggy bank and get contract
    #     # Guard against total_final being None (e.g. for budgets or partially built invoices)
    #     total_final_value = instance.total_final or 0
    #     total_paid = check_piggy_bank(instance, total_final_value, True) if total_final_value > 0 else 0
    #     instance_contract = _get_invoice_contract(instance)
        
    #     if instance.total_final - instance.left_to_pay != total_paid:
    #         instance.left_to_pay = instance.total_final - total_paid
        
    #     # Create payment if needed
    #     new_payment = None
    #     if not ((instance.left_to_pay != 0) ^ (instance.total_final != 0)) or instance.is_suppressed:
    #         new_payment = Payment.objects.create(
    #             token=f"{instance.token}01",
    #             name=instance.title_final,
    #             invoice=instance,
    #             contract=instance_contract,
    #             customer_final=instance.customer_final,
    #             customer_token_final=instance.customer_token_final,
    #             payer_final=instance.payer_final,
    #             payer_token_final=instance.payer_token_final,
    #             amount=instance.total_final - total_paid if instance.total_final else 0,
    #             payment_type=instance.payment_type_final if instance.left_to_pay != 0 else payment_balance.name,
    #             payment_type_token= payment_balance.token if instance.left_to_pay == 0 else instance.payment_type_token_final if instance.payment_type_token_final else None,
    #             payment_bank=instance.payment_bank_final if instance.payment_bank_final and instance.left_to_pay != 0 else None,
    #             payment_swift=instance.payment_swift_final if instance.payment_swift_final and instance.left_to_pay != 0 else None,
    #             address_final=instance.address_final,
    #             location_final=instance.location_final,
    #             due_date=base_date,
    #             status=payment_status_payoff if instance.status == status_payoff else payment_status_pending if instance.left_to_pay != 0 else payment_status_paid,
    #             payment_date= instance.issue_date if instance.left_to_pay != 0 else payment_date if instance.payment_type_token_final == direct_debit_token else None,
    #         )
    #     if instance.left_to_pay == 0 and instance.status != status_payoff:
    #         instance.status = status_paid
    #         instance.payment_bank_final = None
    #         instance.payment_swift_final = None
    #         instance.payment_type_token_final = payment_balance.token
    #         instance.payment_type_final = payment_balance.name
    #         instance.payment_type = payment_balance
            
        
    #     instance._skip_signal = True
        
    #     # Update due_date if needed
    #     current_due_date = _parse_date(instance.due_date)
    #     if due_date:
    #         instance.due_date = due_date
    #     else:
    #         instance.due_date = base_date if (current_due_date and current_due_date < base_date) or not current_due_date else current_due_date
    #     if send_at:
    #         instance.send_at = send_at
            
    #     if instance.status == status_payoff:
    #         instance.due_date = datetime.datetime.now().date()
        
    #     # Determine invoice serie
    #     if instance.is_suppressed:
    #         serie_token = config_values['token_returned_invoice_serie']
    #     elif instance.is_general:
    #         serie_token = config_values['token_general_invoice_serie']
    #     elif instance.refactored_token:
    #         serie_token = config_values['token_refactored_invoice_serie']
    #     else:
    #         serie_token = config_values['token_ordinary_invoice_serie']
        
    #     serie = InvoiceSerie.objects.get(token=serie_token)
    #     instance.simplified = False
    #     invoice_type = config_values['invoice_type_invoice_token']
    #     date_str = instance.issue_date.strftime('%Y%m')
    #     instance.serie = serie
    #     instance.serie_final = generate_serie_final(
    #         serie.token, date_str,
    #         invoice_type=invoice_type,
    #         exclude_status_token=status_pending_token,
    #         invoice=instance,
    #     )
    #     instance.serie_token_final = serie.token

    #     if hasattr(instance, '_generate_verifactu'):
    #         single_batch = False if hasattr(instance, '_bulk_batch') else True
    #         create_verifactu_invoice(instance, single_batch=single_batch)
    #     instance.save()
    #     if genPdf:
    #         generate_report_invoice_pdf(instance)
    
    # Handle cancelled status
    # cancel already handled in another signal
    """ if instance.status == status_cancelled:
        payment_status_cancelled = PaymentStatus.objects.get(token=config_values['payment_status_cancelled_token'])
        Payment.objects.filter(invoice=instance).update(status=payment_status_cancelled) """
            
@receiver(post_save, sender=Payment)
def update_payment(sender, instance, created, **kwargs):
    # No executar durant la càrrega de fixtures
    if kwargs.get('raw', False):
        return
        
    print("update_payment signal connected")
    pre_save.disconnect(payment_status_changed, Payment)
    """
    Signal que s'executa quan es crea o actualitza un pagament.
    Actualitza l'estat de la factura associada segons l'estat del pagament:
    - Si el pagament està pagat, marca la factura com a pagada
    - Si el pagament està vençut, marca la factura com a vençuda
    - Si el pagament està en dotació, marca la factura com a dotació
    - Si el pagament és irrecuperable, marca la factura com a irrecuperable
    """
    if not instance.id or hasattr(instance, "_skip_signal") or created:
        return

    request = None
    if hasattr(sender, 'request') and isinstance(sender.request, Request):
        request = sender.request
    elif hasattr(instance, '_request') and isinstance(instance._request, Request):
            request = instance._request
    user = None
    if request and request.user and request.user.is_authenticated:
        user = request.user
    direct_debit_token = ConfigProject.objects.get(token='direct_debit_token').value
    print(f"Payment {instance.id} is updated")
    payment_status_map = get_status_map()
    status = payment_status_map["payment_status_paid_token"]
    status_expired = payment_status_map["payment_status_expired_token"]
    status_endowment = payment_status_map["payment_status_endowment_token"]
    status_irrecoverable = payment_status_map["payment_status_irrecoverable_token"]
    status_returned = payment_status_map["payment_status_returned_token"]
    status_cancelled = payment_status_map["payment_status_cancelled_token"]
    status_commitment = payment_status_map["payment_status_commitment_token"]
    payment_piggy = payment_status_map["payment_status_piggy_token"]
    commitment_cancelled = ConfigProject.objects.get(token='commitment_deposit_status_cancelled_token').value
    
    #
    #   UPDATE IN CASE OF COMMITMENT DEPOSIT
    #
    
    if instance.status == status and instance.payment_type_token != direct_debit_token and not instance.payment_date:
        payment_date = timezone.now().date()
        instance.payment_date = payment_date
    
    if not instance.invoice or instance.invoice == None:
        if not instance.commitment_deposit or instance.commitment_deposit == None or instance.status != status:
            return
        wallet_payment_deposit_update(instance, user, request)
        return

    #
    #   CONTINUE UPDATE FOR INVOICE
    #
    
    invoice = instance.invoice
    invoice._skip_signal = True
    
    if instance.status == status or instance.status == payment_piggy:
        log_invoice_status(invoice, get_invoice_status("invoice_status_paid_token"), user)
        # Basar-se en l'import cobrat en lloc de requerir que TOTS els Payment històrics
        # estiguin pagats: un intent antic fallit (vençut/retornat) mai passa a "pagat"
        # i bloquejaria la factura per sempre. left_to_pay NO es toca aquí: només es
        # defineix a la creació/confirmació de la factura (total_final, o total_final
        # menys saldo/moneder si es generen 2 payments).
        total_paid = sum(
            (payment.amount or 0)
            for payment in invoice.payments.filter(status__in=[status, payment_piggy])
        )
        remaining = float(invoice.total_final or 0) - float(total_paid)
        invoice_fully_paid = remaining <= 0
        if invoice_fully_paid:
            invoice.status = get_invoice_status("invoice_status_paid_token")
            invoice.save()
        if instance.status == status:
            try:
                commitment_deposit = CommitmentDeposit.objects.filter(invoices=invoice).exclude(status__token=commitment_cancelled).get()
                commitment_deposit.remaining_to_share -= instance.amount
                commitment_deposit.save()
                
                log_data ={
                    "object": commitment_deposit,
                    "previous_status": commitment_deposit.status,
                    "current_status": commitment_deposit.status,
                    "previous_remaining": commitment_deposit.remaining,
                    "current_remaining": commitment_deposit.remaining,
                    "used_remaining": instance.amount,
                    "paid_invoice": invoice if invoice_fully_paid else None,
                    "paid_invoice_payment": instance,
                    "user": user,
                }
                log = LogCommitmentDepositMovement.objects.create(**log_data)
                
            except CommitmentDeposit.DoesNotExist:
                pass
        
        instance._skip_signal = True
        instance.save()
    elif instance.status == status_expired:
        log_invoice_status(invoice, get_invoice_status("invoice_status_expired_token"), user)
        invoice.status = get_invoice_status("invoice_status_expired_token")
        invoice.save()
        
        contract = invoice.contract if invoice.contract else None
        if contract:
            contract.last_debt_data = instance.payment_date
            contract.save()
        
        print(f"Invoice {invoice.id} marked as {status_expired.name}")
    elif instance.status == status_returned:
        log_invoice_status(invoice, get_invoice_status("invoice_status_confirmed_token"), user)
        invoice.status = get_invoice_status("invoice_status_confirmed_token")
        invoice.save()
    elif instance.status == status_endowment:
        log_invoice_status(invoice, get_invoice_status("invoice_status_endowment_token"), user)
        invoice.status = get_invoice_status("invoice_status_endowment_token")
        invoice.save()
    elif instance.status == status_irrecoverable:
        log_invoice_status(invoice, get_invoice_status("invoice_status_irrecoverable_token"), user)
        invoice.status = get_invoice_status("invoice_status_irrecoverable_token")
        invoice.save()
    elif instance.status == status_commitment:
        log_invoice_status(invoice, get_invoice_status("invoice_status_commitment_token"), user)
        invoice.status = get_invoice_status("invoice_status_commitment_token")
        invoice.save()
    elif instance.status == status_cancelled:
        log_invoice_status(invoice, get_invoice_status("invoice_status_cancelled_token"), user)
        invoice.status = get_invoice_status("invoice_status_cancelled_token")
        invoice.save()
    pre_save.connect(payment_status_changed, Payment)


    
""" @receiver(post_save, sender=Payment)
def surcharge_invoice(sender, instance, **kwargs):
    if instance.id:
        print(f"Surcharge {instance.id} is updated")
        if hasattr(instance, '_skip_signal'):
            return
        status_returned = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_returned_token').value)
        #status_expired = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_expired_token').value)
        if (instance.status == status_returned) :
            instance._skip_signal = True
            print(f"Skip signal for surcharge {instance.id}")
            print("INVOICE FOR PAYMENT: ", instance.invoice)
            invoice = instance.invoice
            if invoice.parent_invoice:
                while invoice.parent_invoice:
                    invoice = invoice.parent_invoice
            surcharge = invoice_return_charge(invoice, 'RECLAMACIÓ DE SERVEI') """

@receiver(pre_save, sender=Payment)
def update_contract_debt(sender, instance, **kwargs):
    # No executar durant la càrrega de fixtures
    if kwargs.get('raw', False):
        return
        
    print("update_contract_debt signal connected")
    #if previous payment status is expired and now is paid, update contract debt
    if instance.id:
        try:
            old_instance = Payment.objects.get(id=instance.id)
            expired_status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_expired_token').value)
            paid_status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)
            if old_instance.status == expired_status and instance.status == paid_status:
                contract = instance.invoice.contract if instance.invoice else None
                if not contract:
                    contract = instance.commitment_deposit.contract if instance.commitment_deposit else None
                if contract:
                    contract.last_debt_data = instance.payment_date
                    contract.save()
        except Payment.DoesNotExist:
            # L'objecte no existeix a la base de dades (per exemple, durant la càrrega de fixtures)
            # No fem res en aquest cas
            pass
        except Exception as e:
            print("error: ", e)
            pass

@receiver(post_save, sender=Invoice)
def check_paid_invoice(sender, instance, **kwargs):
    """
    Signal que s'executa quan es guarda una factura.
    Comprova si la factura està pagada i actualitza els ClaimRequestPayment associats.
    """
    # No executar durant la càrrega de fixtures
    if kwargs.get('raw', False):
        return
    
    if hasattr(instance, '_skip_signal_updating_verifactu'):
        return
    
    if instance.status and instance.status.token == ConfigProject.objects.get(token='invoice_status_paid_token').value:
        from order.middleware import get_current_user
        user = get_current_user()
        # Obtenim els ClaimRequestPayment associats a la factura
        bail_paid_token = ConfigProject.objects.get(token='bail_status_returned_token').value
        bails = Bail.objects.filter(invoice=instance).exclude(status__token=bail_paid_token)
        if bails.count() > 0:
            for bail in bails:
                LogBailStatus.objects.create(
                    object=bail,
                    previous_status=bail.status,
                    current_status=BailStatus.objects.get(token=bail_paid_token),
                    user=user,
                )
                payment_date = instance.payments.order_by('-payment_date').first().payment_date if instance.payments.exists() else timezone.now().date()
                bail.payment_date = payment_date
                bail.return_date = payment_date
                bail.status = BailStatus.objects.get(token=bail_paid_token)
                bail.save()
        claim_payments = ClaimRequestPayment.objects.filter(payment__invoice=instance)
        
        # Actualitzem els camps is_paid i is_vulnerable
        for claim_payment in claim_payments:
            claim_payment.is_paid = True
            vulnerable_status_approved = VulnerabilityRequestStatus.objects.get(token=ConfigProject.objects.get(token='vulnerability_request_status_accepted_token').value)
            vulnerability_request = VulnerabilityRequest.objects.filter(claim_request=claim_payment.claim_request, status=vulnerable_status_approved)
            claim_payment.is_vulnerable = instance.contract and vulnerability_request.exists() if instance.contract else False
            claim_payment.save()
            
            # Si tots els pagaments estan pagats, marquem el contracte com a exclòs
            if claim_payment.contract:
                all_payments_paid = not ClaimRequestPayment.objects.filter(
                    contract=claim_payment.contract,
                    is_paid=False
                ).exists()
                
                if all_payments_paid:
                    claim_payment.is_excluded = True
                    claim_payment.save()
                    
                    # Creem un log de l'acció
                    
                    LogClaimRequestContractChange.objects.create(
                        object=claim_payment.claim_request,
                        deleted_contract=claim_payment.contract,
                        amount_paid=instance.total_final,
                        user=user,
                    )

@receiver(post_save, sender=Invoice)
def check_cancel_invoice(sender, instance, **kwargs):
    # No executar durant la càrrega de fixtures
    if kwargs.get('raw', False):
        return
        
    if hasattr(instance, '_skip_signal_updating_verifactu'):
        return
        
    post_save.disconnect(check_paid_invoice, sender=Invoice)
    post_save.disconnect(create_payment_invoice, sender=Invoice)
    post_save.disconnect(update_payment, sender=Payment)
    pre_save.disconnect(update_contract_debt, sender=Payment)
    if instance.id:  
        status_cancelled_token = ConfigProject.objects.get(token='invoice_status_cancelled_token').value
        if instance.status and instance.status.token == status_cancelled_token:
            invoice_payments = Payment.objects.filter(invoice=instance)
            status_payment_paid_token = ConfigProject.objects.get(token='payment_status_paid_token').value
            for payment in invoice_payments:
                if payment.status.token == status_payment_paid_token:
                    contract = payment.contract
                    if not contract:
                        if payment.commitment_deposit:
                            contract = payment.commitment_deposit.contract
                        elif payment.invoice:
                            if payment.invoice.contract:
                                contract = payment.invoice.contract
                            elif payment.invoice.contract_request:
                                contract = Contract.objects.get(contract_request=payment.invoice.contract_request)
                            elif payment.invoice.contract_termination:
                                contract = payment.invoice.contract_termination.contract
                    if contract:
                        piggy_bank = contract.piggy_bank
                        piggy_bank.amount += payment.amount
                        piggy_bank.save()
                        piggy_bank_movement = PiggyBankMovement.objects.create(
                            token=generate_token(PiggyBankMovement),
                            piggy_bank=piggy_bank,
                            amount=payment.amount,
                            is_positive=True,
                            movement_date=timezone.now(),
                            payment=payment,
                        )
                    else:
                        language = config("LANGUAGE", default="ca")
                        with translation.override(language):
                            name = _("Invoice %(token)s cancelled with pending balance") % {"token": instance.token}
                            description = _("Invoice %(token)s cancelled with payment collected of %(amount)s€") % {
                                "token": instance.token,
                                "amount": payment.amount,
                            }
                        Notification.objects.create(
                            token=generate_token(Notification),
                            name=name,
                            description=description,
                            module="billing",
                            entity="invoice",
                            object_id=instance.id
                        )
                payment.status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_cancelled_token').value)
                payment.save()
                
    post_save.connect(check_paid_invoice, sender=Invoice)
    post_save.connect(update_payment, sender=Payment)
    pre_save.connect(update_contract_debt, sender=Payment)
    post_save.connect(create_payment_invoice, sender=Invoice)


@receiver(pre_save, sender=Payment)
def payment_status_changed(sender, instance, **kwargs):
    # No executar durant la càrrega de fixtures
    if kwargs.get('raw', False):
        return
        
    print("payment_status_changed signal connected")
    if instance.pk:
        try:
            original_instance = sender.objects.get(pk=instance.pk)
            paid_token = ConfigProject.objects.get(token='payment_status_paid_token').value
            """ if original_instance.status.token == paid_token and instance.status.token == paid_token:
                
                #create a copy of the payment
                payment_copy = Payment.objects.create(
                    token=instance.token[:-2] + str(int(instance.token[-2:]) + 1).zfill(2),
                    name='(DUPLICAT) ' + instance.name if instance.name else '(DUPLICAT)',
                    status=instance.status,
                    contract=instance.contract,
                    commitment_deposit=instance.commitment_deposit,
                    amount=instance.amount,
                    sent_date=instance.sent_date,
                    due_date=instance.due_date,
                    payment_type=instance.payment_type,
                    payment_type_token=instance.payment_type_token,
                    payment_date=timezone.now(),
                    payment_bank=instance.payment_bank,
                    payment_swift=instance.payment_swift,
                    customer_final=instance.customer_final,
                    customer_token_final=instance.customer_token_final,
                    payer_final=instance.payer_final if instance.payer_final else instance.customer_final,
                    payer_token_final=instance.payer_token_final if instance.payer_token_final else instance.customer_token_final,
                    address_final=instance.address_final,
                    location_final=instance.location_final,
                    document=instance.document,
                    is_duplicate=True,
                )
                contract = instance.contract
                if contract:
                    piggy_bank = contract.piggy_bank
                    piggy_bank.amount += instance.amount
                    piggy_bank.save()
                    piggy_bank_movement = PiggyBankMovement.objects.create(
                        token=generate_token(PiggyBankMovement),
                        piggy_bank=piggy_bank,
                        amount=instance.amount,
                        is_positive=True,
                        movement_date=timezone.now(),
                        payment=payment_copy,
                    ) """
            
            if original_instance.status != instance.status:
                request = None
                if hasattr(sender, 'request') and isinstance(sender.request, Request):
                    request = sender.request
                elif hasattr(instance, '_request') and isinstance(instance._request, Request):
                        request = instance._request
                user = None
                if request and request.user:
                    user = request.user
                
                print(
                    f"Payment status changed from {original_instance.status} "
                    f"to {instance.status} for Payment ID: {instance.pk}"
                )
                
                log_payment_status(original_instance, instance.status, user, instance.payment_date, instance.payment_type_token)
                movement_date = instance.payment_date if instance.status.token == paid_token else timezone.now()
                generate_payment_movement(
                    original_instance, instance.status, 
                    movement_date, instance.payment_type_token, 
                    instance.payment_bank, user,
                    None, 
                    instance.remittances.filter(sent_at__isnull=False).order_by('-sent_at').first()
                    )
            
        except Exception as e:
            print(e)
            pass


@receiver(pre_save, sender=CommitmentDeposit)
def commitment_deposit_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = CommitmentDeposit.objects.get(pk=instance.pk)
            cancelled_token = ConfigProject.objects.get(token='commitment_deposit_status_cancelled_token').value
            if instance.status and instance.status.token == cancelled_token and (not old_instance.status or old_instance.status.token != cancelled_token):
                cascade_commitment_deposit_cancellation(instance)
        except Exception as e:
            print(f"Error in commitment_deposit_pre_save: {e}")

def cascade_commitment_deposit_cancellation(deposit):
    from billing.models import PaymentCommitment, PaymentCommitmentStatus, Payment, PaymentStatus
    from coredata.models import ConfigProject
    from notification.models import Notification
    import uuid

    try:
        # Status tokens
        pc_paid_token = ConfigProject.objects.get(token='payment_commitment_status_paid_token').value
        pc_cancelled_token = ConfigProject.objects.get(token='payment_commitment_status_cancelled_token').value
        
        p_paid_token = ConfigProject.objects.get(token='payment_status_paid_token').value
        p_cancelled_token = ConfigProject.objects.get(token='payment_status_cancelled_token').value
        p_sent_token = ConfigProject.objects.get(token='payment_status_sent_token').value # "GENERAT"

        pc_cancelled_status = PaymentCommitmentStatus.objects.get(token=pc_cancelled_token)
        p_cancelled_status = PaymentStatus.objects.get(token=p_cancelled_token)

        # 1. Update PaymentCommitments
        PaymentCommitment.objects.filter(
            commitment_deposit=deposit
        ).exclude(
            status__token__in=[pc_paid_token, pc_cancelled_token]
        ).update(status=pc_cancelled_status)

        # 2. Update Payments
        payments = Payment.objects.filter(commitment_deposit=deposit).exclude(
            status__token__in=[p_paid_token, p_cancelled_token]
        )

        for payment in payments:
            if payment.status.token == p_sent_token:
                # Notify user or mark for manual review
                Notification.objects.create(
                    token=str(uuid.uuid4()),
                    name="Pagament en remesa d'un compromís cancel·lat",
                    description=f"El pagament {payment.token} del compromís {deposit.token} està en estat GENERAT (en remesa) i el compromís s'ha cancel·lat. Cal revisió manual.",
                    module="billing",
                    entity="payment",
                    object_id=str(payment.id),
                    is_active=True
                )
            else:
                payment.status = p_cancelled_status
                payment.save()
    except Exception as e:
        print(f"Error in cascade_commitment_deposit_cancellation: {e}")
            


@receiver(pre_delete, sender=Reading)
def reading_estimated_bag_fix(sender, instance, **kwargs):
    print("reading_estimated_bag_fix signal connected")
    if kwargs.get('raw', False):
        return
        
    if instance.id:
        try:
            original_instance = sender.objects.get(pk=instance.pk)
            estimated_movement = EstimatedBagMovement.objects.filter(reading=original_instance, is_positive=True).first()
            if estimated_movement:
                print(f"Estimated movement found for reading {estimated_movement.id}")
                EstimatedBagMovement.objects.create(
                    token=generate_token(EstimatedBagMovement),
                    estimated_bag=estimated_movement.estimated_bag,
                    amount=estimated_movement.amount,
                    is_positive=False,
                    movement_date=timezone.now(),
                )
                estimated_movement.estimated_bag.total_consumption -= estimated_movement.amount
                estimated_movement.estimated_bag.save()
                estimated_movement.delete()
        except Exception as e:
            print(e)