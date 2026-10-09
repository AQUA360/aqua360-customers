from http.client import PAYMENT_REQUIRED
import re
from django.utils import timezone
from billing.models import CommitmentDeposit, DocumentSEPA, DocumentSEPALine, Invoice, Payment, PaymentMovement, PaymentStatus
from billing.utils.invoice_service import change_status_logger
from contract.models import Contract, PaymentType, PiggyBank, PiggyBankMovement
from coredata.models import ConfigProject
from coredata.utils.name_utils import generate_token
from logger.models import LogPaymentStatusChange
from pricing.models import ProductOrigin
from django.db.models import Q
from django.db.models.signals import post_save, pre_save

def generate_mandate_id(general_payment, mandate_token, overwrite = None):
    # mandate token = contract/connection token
    # continue sequence = True if found difference in payment/iban
    # is new mandate = True if new mandate is being created
    
    #
    # FORMAT
    # MANDATE_TOKEN + P + GENERAL_PAYMENT_ID + S + SEQUENCE (001)
    # EX: 123456789P1500S002
    #
    
    if not general_payment:
        print("ERROR: NO GENERAL PAYMENT")
        return
    clean_mandate_token = re.sub(r'[^a-zA-Z0-9]', '', mandate_token)
    sequence = "000"
    
    previous_own_mandate = general_payment.mandate_logs.filter(
        is_manual=False
    ).order_by('-created_at').first()
    
    
    if previous_own_mandate and "S" in previous_own_mandate.new_mandate_id:
        sequence = previous_own_mandate.new_mandate_id.split("S")[1]
        sequence = int(sequence) + 1
        sequence = str(sequence).zfill(3)
    mandate_id = f"{clean_mandate_token}P{general_payment.id}S{sequence}"
    return mandate_id


# Permet personalitzar per client: si existeix generate_mandate_id_personalized,
# s'usa la seva generate_mandate_id en lloc de la d'aquest mòdul.
try:
    from billing.utils import generate_mandate_id_personalized
    if hasattr(generate_mandate_id_personalized, 'generate_mandate_id'):
        generate_mandate_id = generate_mandate_id_personalized.generate_mandate_id
except ImportError:
    pass



def get_payment_SEPA_data(payments, payment_data):
    print("\n\nGET PAYMENT SEPA DATA (DEPRECATED)")
    print(payments)
    try:
        lines = DocumentSEPALine.objects.filter(payments__in=payments)
        document = DocumentSEPA.objects.filter(lines__in=lines).first()
        if not document:
            document = DocumentSEPA.objects.create()
        print("document")
        print(document)
        try:
            lines.delete()
        except:
            raise Exception("Error deleting temp lines")
    except:
        document = DocumentSEPA.objects.create()
    """ 
    try:
        lines = DocumentSEPALine.objects.filter(payments__in=payments)
        print("lines")
        print(lines)
        prev_document = DocumentSEPA.objects.filter(lines__in=lines)
        prev_document.delete()
    except:
        print("problem deleting previous document")
        pass
    document = DocumentSEPA.objects.create()
    """
    origins = []
    payment_origins = payment_data['origins']
    date_start = payment_data['start_date']
    date_end = payment_data['end_date']
    for origin in payment_origins:
        origins.append(ProductOrigin.objects.get(id=origin))
    grouped_payments = {}
    anomalies = {}
    invoices = []
    commitment_deposits = []
    status_pending = ConfigProject.objects.get(token='payment_status_pending_token').value
    payment_status = PaymentStatus.objects.get(token=status_pending)

    for payment_id in payments:
        print("\n\nPAYMENT ID")
        print(payment_id)
        payment = Payment.objects.get(id=payment_id)
        address = ""
        location = ""
        if payment.invoice:
            invoice = payment.invoice.id
            invoices.append(invoice)
            customer_token = payment.invoice.customer_token_final
            customer_name = payment.invoice.customer_final
            address = payment.invoice.address_final if payment.invoice.address_final else ''
            location = payment.invoice.location_final if payment.invoice.location_final else ''
        if payment.commitment_deposit:
            commitment_deposit = payment.commitment_deposit.id
            commitment_deposits.append(commitment_deposit)
            customer_token = payment.commitment_deposit.contract.holder.token
            customer_name = f'{payment.commitment_deposit.contract.holder.name} {payment.commitment_deposit.contract.holder.surname}'
            address_instance = payment.commitment_deposit.contract.address_billing.address if payment.commitment_deposit.contract.address_billing and payment.commitment_deposit.contract.address_billing.address else None
            address = f"{address_instance.street} {address_instance.street_number}" if address_instance else ''
            location = f"{address_instance.postal_code} {address_instance.city}, {address_instance.province} - {address_instance.country}" if address_instance else ''
        
        
        payment_iban = payment.payment_bank
        payment_swift = payment.payment_swift
        amount = float(payment.amount)

        key = f"{payment_iban}_{customer_token}"

        if payment_iban in grouped_payments:
            if customer_token in grouped_payments[payment_iban]:
                grouped_payments[payment_iban][customer_token]['amount'] += amount
                grouped_payments[payment_iban][customer_token]['payment_ids'].append(payment_id)
            else:
                if customer_token not in anomalies:
                    anomalies[key] = {'amount': 0, 'count': 0}
                
                anomalies[key]['amount'] += amount
                anomalies[key]['token'] = customer_token
                anomalies[key]['iban'] = payment_iban
                anomalies[key]['swift'] = payment_swift
                anomalies[key]['tax_name'] = customer_name
                anomalies[key]['due_date'] = payment.due_date
                anomalies[key]['count'] += 1

                grouped_payments[payment_iban][customer_token] = {
                    'amount': amount,
                    'iban': payment_iban,
                    'swift': payment_swift if payment_swift else '',
                    'tax_name': customer_name,
                    'due_date': payment.due_date,
                    'address': address,
                    'location': location,
                    'is_anomaly': True  
                }
                if 'payment_ids' not in grouped_payments[payment_iban][customer_token]:
                    grouped_payments[payment_iban][customer_token]['payment_ids'] = []

                # Now append the payment ID to the payment_ids array
                grouped_payments[payment_iban][customer_token]['payment_ids'].append(payment_id)

                # Mark all payments under this IBAN as anomalies
                for other_token in grouped_payments[payment_iban]:
                    grouped_payments[payment_iban][other_token]['is_anomaly'] = True
        else:
            grouped_payments[payment_iban] = {
                customer_token: {
                    'amount': amount,
                    'iban': payment_iban,
                    'swift': payment_swift if payment_swift else '',
                    'tax_name': customer_name,
                    'due_date': payment.due_date,
                    'address': address,
                    'location': location,
                    'is_anomaly': False
                }
            }
            if 'payment_ids' not in grouped_payments[payment_iban][customer_token]:
                    grouped_payments[payment_iban][customer_token]['payment_ids'] = []
            grouped_payments[payment_iban][customer_token]['payment_ids'].append(payment_id)
    
    document.invoices.set(invoices)
    document.commitment_deposits.set(commitment_deposits)
    document.save()
    # Sort grouped_payments so anomalies come first within each IBAN
    for iban in grouped_payments:
        grouped_payments[iban] = dict(sorted(
            grouped_payments[iban].items(),
            key=lambda item: not item[1]['is_anomaly']
        ))
    
    # Save grouped payments to the database
    for iban, customers in grouped_payments.items():
        for token, data in customers.items():
            line = DocumentSEPALine.objects.create(line_number=len(grouped_payments.items()))
            payments_to_add = Payment.objects.filter(payment_bank=iban, status=payment_status, id__in=payments)
            if date_start and date_end:
                payments_to_add = payments_to_add.filter(payment_date__range=(date_start, date_end))
            elif date_start:
                payments_to_add = payments_to_add.filter(payment_date__gte=date_start)
            elif date_end:
                payments_to_add = payments_to_add.filter(payment_date__lte=date_end)

            for payment in payments_to_add:
                if payment.invoice:
                    if payment.invoice.origin in origins:
                        line.payments.add(payment)
                if payment.commitment_deposit:
                    line.payments.add(payment)
            document.lines.add(line)

    print("\n\nGrouped payments (sorted with anomalies first):")
    for iban, customers in grouped_payments.items():
        print(f"IBAN {iban}")
        for token, data in customers.items():
            print(f"Customer {token} - {data['amount']} - {'Anomaly' if data['is_anomaly'] else 'Normal'}")
            print(data)

    print("\n\nAnomalies:")
    for key, data in anomalies.items():
        print(f"IBAN {key.split('_')[0]} - {key.split('_')[1]} - {data['amount']} - {data['count']}")

    return document, anomalies, grouped_payments

def get_sii_invoices(data):
    issue_start_date = data.get("issue_start_date", None)
    issue_end_date = data.get("issue_end_date", None)
    expire_start_date = data.get("expire_start_date", None)
    expire_end_date = data.get("expire_end_date", None)
    invoice_statuses = data.get("invoice_statuses", [])
    invoice_series = data.get("invoice_series", [])
    origin_ids = data.get("origin", [])
    
    invoice_filter = Q()
    if issue_start_date == issue_end_date:
        invoice_filter &= Q(issue_date=issue_start_date)
    else:
        invoice_filter &= Q(issue_date__range=(issue_start_date, issue_end_date))
    
    if invoice_statuses and len(invoice_statuses) > 0:
        invoice_filter &= Q(status__id__in=invoice_statuses)
    if invoice_series and len(invoice_series) > 0:
        invoice_filter &= Q(serie__id__in=invoice_series)
    if origin_ids and len(origin_ids) > 0:
        invoice_filter &= Q(origin__id__in=origin_ids)
    
    invoices = Invoice.objects.filter(invoice_filter)
    return invoices

def get_status_map():
    tokens = [
        "payment_status_paid_token",
        "payment_status_pending_token",
        "payment_status_expired_token",
        "payment_status_commitment_token",
        "payment_status_endowment_token",
        "payment_status_irrecoverable_token",
        "payment_status_sent_token",
        "payment_status_returned_token",
        "payment_status_cancelled_token",
        "payment_status_piggy_token",
        "payment_status_payoff_token"
    ]
    return {
        token: PaymentStatus.objects.get(token=ConfigProject.objects.get(token=token).value)
        for token in tokens
    }

def log_payment_status(payment, payment_status, user, payment_date=None, payment_type_token=None):
    paid_token = ConfigProject.objects.get(token='payment_status_paid_token').value
    piggy_token = ConfigProject.objects.get(token='payment_status_piggy_token').value
    LogPaymentStatusChange.objects.create(
        object=payment,
        previous_status=payment.status,
        current_status=payment_status,
        used_payment_token=payment_type_token if payment_type_token else payment.payment_type_token,
        user=user,
        timestamp= payment_date if payment_status.token in [paid_token, piggy_token] and payment_date else timezone.now()
    )

def generate_payment_movement(payment, payment_status, payment_date, payment_type_token, payment_bank, user, reject_motive = None, payment_remittance = None, add_bank = False):
    # DECLARING PAYMENT TYPE SINCE WHEN PAYING MANUALy PAYMENT TYPE CHANGES LIKE STATUS (NOT SAME AS CURRENT IN PAYMENT)
    paid_status_token = ConfigProject.objects.get(token='payment_status_paid_token').value
    piggy_status_token = ConfigProject.objects.get(token='payment_status_piggy_token').value
    cancelled_status_token = ConfigProject.objects.get(token='payment_status_cancelled_token').value
    payoff_status_token = ConfigProject.objects.get(token='payment_status_payoff_token').value
    
    """ if payment_status.token == cancelled_status_token:
        return None """
    
    try:
        payment_type = PaymentType.objects.get(token=payment_type_token)
    except Exception as e:
        print(e)
        payment_type = None
    is_positive = None
    if payment_status.token in [paid_status_token]:
        is_positive = True
    if payment.status.token in [paid_status_token, cancelled_status_token] or payment_status.token in [payoff_status_token, piggy_status_token]:
        is_positive = False
    
    if is_positive is None:
        return None
    if not payment_date:
        raise Exception("Payment date is required")
    
    new_movement = PaymentMovement.objects.create(
        token = generate_token(PaymentMovement),
        user = user,
        payment = payment,
        movement_date = payment_date,
        payment_type = payment_type,
        payment_bank = payment_bank if payment_type_token == "DIRECT_DEBIT" or add_bank else None,
        previous_status = payment.status,
        current_status = payment_status,
        reject_motive = reject_motive,
        payment_remittance = payment_remittance if payment_type_token == "DIRECT_DEBIT" or add_bank else None,
        is_positive = is_positive,
        payment_origin = payment.payment_origin_choice,
        is_active = True,
    )
    return new_movement

def log_invoice_status(invoice, invoice_status, current_user=None):
    if not current_user:
        from order.middleware import get_current_user
        current_user = get_current_user()
    change_status_logger(current_user, invoice, invoice_status)

def disconnect_payment_signals():
    from billing.signals import check_cancel_invoice, check_paid_invoice, create_payment_invoice, payment_status_changed, update_payment, update_contract_debt
    post_save.disconnect(check_paid_invoice, sender=Invoice)
    post_save.disconnect(create_payment_invoice, sender=Invoice)
    post_save.disconnect(check_cancel_invoice, sender=Invoice)
    post_save.disconnect(update_payment, sender=Payment)
    pre_save.disconnect(payment_status_changed, sender=Payment)
    pre_save.disconnect(update_contract_debt, sender=Payment)

def reconnect_payment_signals():
    from billing.signals import check_cancel_invoice, check_paid_invoice, create_payment_invoice, payment_status_changed, update_payment, update_contract_debt
    post_save.connect(update_payment, sender=Payment)
    pre_save.connect(update_contract_debt, sender=Payment)
    post_save.connect(check_paid_invoice, sender=Invoice)
    post_save.connect(create_payment_invoice, sender=Invoice)
    pre_save.connect(payment_status_changed, sender=Payment)
    post_save.connect(check_cancel_invoice, sender=Invoice)