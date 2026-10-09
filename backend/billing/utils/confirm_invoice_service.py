import datetime

from django.db import transaction

from billing.models import Invoice, InvoiceSerie, InvoiceStatus, Payment, PaymentStatus
from contract.models import PaymentType
from coredata.models import ConfigProject
from dateutil.relativedelta import relativedelta
import calendar

from verifactu.utils.save_verifactu_info import create_verifactu_invoice

# Mapping InvoiceStatus.token -> PaymentStatus.token.
# Pre-factura (1) is the only status where no payment is created.
INVOICE_STATUS_TOKEN_PREFACTURA = '1'

INVOICE_TO_PAYMENT_STATUS_TOKEN = {
    '0': '0',    # Pagada -> Pagat
    '-1': '-1',  # Vençuda -> Vençut
    '2': '1',    # Confirmada -> Pendent
    '-3': '1',   # Morositat -> Pendent
    '4': '4',    # En compromís -> En compromís
    '-5': '-5',  # Irrecuperable -> Irrecuperable
    '-6': '-6',  # Anul·lada -> Anul·lat
    '-4': '1',   # Parcialment Irrecuperable -> Pendent
    '-2': '-4',  # Abonament -> Abonament
}


def get_payment_status_token_for_invoice_status(invoice_status_token):
    if invoice_status_token == INVOICE_STATUS_TOKEN_PREFACTURA:
        return None
    return INVOICE_TO_PAYMENT_STATUS_TOKEN.get(invoice_status_token, '1')


def get_invoice_status_tokens_excluded_from_payment_creation():
    try:
        return [ConfigProject.objects.get(token='invoice_status_pending_token').value]
    except ConfigProject.DoesNotExist:
        return [INVOICE_STATUS_TOKEN_PREFACTURA]


def build_invoices_without_active_payment_queryset(billing_id=None):
    queryset = (
        Invoice.objects.filter(is_active=True, is_excluded=False)
        .exclude(payments__is_active=True)
        .distinct()
    )

    if billing_id is not None:
        queryset = queryset.filter(billing_id=billing_id)

    excluded_tokens = get_invoice_status_tokens_excluded_from_payment_creation()
    if excluded_tokens:
        queryset = queryset.exclude(status__token__in=excluded_tokens)

    return queryset.select_related('status', 'contract').order_by('id')


def _parse_date(date_value):
    """Helper function to parse date from various formats."""
    if date_value is None:
        return datetime.datetime.now().date()
    if isinstance(date_value, datetime.date):
        return date_value
    if isinstance(date_value, str):
        try:
            return datetime.datetime.strptime(date_value, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return datetime.datetime.now().date()
    return datetime.datetime.now().date()


def _get_invoice_contract(instance):
    """Helper function to get contract from invoice instance."""
    if instance.contract:
        return instance.contract
    elif instance.contract_termination:
        return instance.contract_termination.contract
    return None


def _get_remittance_date(instance):
    """Helper function to get remittance date from contract or contract_request."""
    if instance.contract:
        return instance.contract.remittance_date
    elif instance.contract_request:
        return instance.contract_request.remittance_date
    return None


def confirm_invoice(instance, generate_verifactu = False, skip_gen_pdf = False, config_cache = None):
    from billing.utils.invoice_service import check_piggy_bank, generate_serie_final
    from billing.views.invoice_pdf_view import generate_report_invoice_pdf
    
    # Check if invoice has line items
    if instance.line_items.count() == 0:
        instance.refresh_from_db()
        
    
    # Batch load all ConfigProject values at once to reduce queries
    config_tokens = [
        'invoice_status_confirmed_token',
        'status_payoff',
        'invoice_status_cancelled_token',
        'invoice_status_pending_token',
        'invoice_status_paid_token',
        'direct_debit_token',
        'payment_status_pending_token',
        'payment_status_paid_token',
        'payment_status_cancelled_token',
        'token_ordinary_invoice_serie',
        'token_returned_invoice_serie',
        'token_refactored_invoice_serie',
        'invoice_type_invoice_token',
        'invoice_status_payoff_token',
        'payment_status_paid_token',
    ]
    if config_cache is not None:
        missing_tokens = [tok for tok in config_tokens if tok not in config_cache]
        if missing_tokens:
            config_cache.update({
                cfg.token: cfg.value 
                for cfg in ConfigProject.objects.filter(token__in=missing_tokens)
            })
        config_values = config_cache
    else:
        config_values = {
            cfg.token: cfg.value 
            for cfg in ConfigProject.objects.filter(token__in=config_tokens)
        }
    
    # Get status objects
    status_confirmed = InvoiceStatus.objects.get(token=config_values['invoice_status_confirmed_token'])
    status_payoff = InvoiceStatus.objects.get(token=config_values['invoice_status_payoff_token'])
    status_prefactura_token = config_values['invoice_status_pending_token']
    status_paid = InvoiceStatus.objects.get(token=config_values['invoice_status_paid_token'])
    is_initial_confirmation = instance.status in (status_confirmed, status_payoff)

    if instance.status.token != status_prefactura_token:
        status_pending_token = config_values['invoice_status_pending_token']
        direct_debit_token = config_values['direct_debit_token']
        payment_status_paid = PaymentStatus.objects.get(token=config_values['payment_status_paid_token'])
        payment_balance = PaymentType.objects.get(token="BALANCE")

        genPdf = not skip_gen_pdf and is_initial_confirmation

        # Delete existing payment if any
        Payment.objects.filter(invoice=instance).delete()
        
        # Calculate dates
        remittance_date = _get_remittance_date(instance)
        base_date = _parse_date(instance.due_date)
        base_send_at = _parse_date(instance.send_at)
        if not instance.due_date:
            base_date = base_date + relativedelta(months=1)
        
        # Calculate payment date based on remittance date
        payment_date = base_date
        due_date = None
        send_at = None
        if remittance_date:
            # Get the last day of the base_date month using calendar.monthrange
            last_day_of_month = calendar.monthrange(base_date.year, base_date.month)[1]
            last_day_of_month_send = calendar.monthrange(base_send_at.year, base_send_at.month)[1]
            remittance_day = min(remittance_date, last_day_of_month)
            remittance_day_send = min(remittance_date, last_day_of_month_send)
            if remittance_day > base_date.day:
                payment_date = datetime.date(base_date.year, base_date.month, remittance_day)
                due_date = payment_date
            if base_send_at and base_send_at.day < remittance_day_send:
                send_at = datetime.date(base_send_at.year, base_send_at.month, remittance_day_send)
        
        # Check piggy bank and get contract
        # Guard against total_final being None (e.g. for budgets or partially built invoices)
        total_final_value = instance.total_final or 0
        total_paid = check_piggy_bank(instance, total_final_value, True) if total_final_value > 0 else 0
        instance_contract = _get_invoice_contract(instance)
        
        if instance.total_final - instance.left_to_pay != total_paid:
            instance.left_to_pay = instance.total_final - total_paid
        
        # Create payment if needed
        new_payment = None
        if not ((instance.left_to_pay != 0) ^ (instance.total_final != 0)) or instance.is_suppressed:
            if instance.left_to_pay != 0:
                payment_status_token = get_payment_status_token_for_invoice_status(
                    instance.status.token
                )
                payment_status = PaymentStatus.objects.get(token=payment_status_token)
            else:
                payment_status = payment_status_paid

            new_payment = Payment.objects.create(
                token=f"{instance.token}01",
                name=instance.title_final,
                invoice=instance,
                contract=instance_contract,
                customer_final=instance.customer_final,
                customer_token_final=instance.customer_token_final,
                payer_final=instance.payer_final,
                payer_token_final=instance.payer_token_final,
                amount=instance.total_final - total_paid if instance.total_final else 0,
                payment_type=instance.payment_type_final if instance.left_to_pay != 0 else payment_balance.name,
                payment_type_token= payment_balance.token if instance.left_to_pay == 0 else instance.payment_type_token_final if instance.payment_type_token_final else None,
                payment_bank=instance.payment_bank_final if instance.payment_bank_final and instance.left_to_pay != 0 else None,
                payment_swift=instance.payment_swift_final if instance.payment_swift_final and instance.left_to_pay != 0 else None,
                address_final=instance.address_final,
                location_final=instance.location_final,
                due_date=base_date,
                status=payment_status,
                payment_date= instance.issue_date if instance.left_to_pay != 0 else payment_date if instance.payment_type_token_final == direct_debit_token else None,
            )
        if instance.left_to_pay == 0 and instance.status != status_payoff:
            instance.status = status_paid
            instance.payment_bank_final = None
            instance.payment_swift_final = None
            instance.payment_type_token_final = payment_balance.token
            instance.payment_type_final = payment_balance.name
            instance.payment_type = payment_balance
            
        
        instance._skip_signal = True

        if is_initial_confirmation:
            # Update due_date if needed
            current_due_date = _parse_date(instance.due_date)
            if due_date:
                instance.due_date = due_date
            else:
                instance.due_date = base_date if (current_due_date and current_due_date < base_date) or not current_due_date else current_due_date
            if send_at:
                instance.send_at = send_at

            if instance.status == status_payoff:
                instance.due_date = datetime.datetime.now().date()

            # Determine invoice serie
            if instance.is_suppressed:
                serie_token = config_values['token_returned_invoice_serie']
            elif instance.refactored_token:
                serie_token = config_values['token_refactored_invoice_serie']
            else:
                serie_token = config_values['token_ordinary_invoice_serie']

            serie = InvoiceSerie.objects.get(token=serie_token)
            instance.simplified = False
            invoice_type = config_values['invoice_type_invoice_token']
            date_str = instance.issue_date.strftime('%Y%m')
            instance.serie = serie
            # `generate_serie_final()` confirma el número de sèrie (incrementa i desa
            # `InvoiceSequence`) en la seva pròpia transacció interna, abans que la
            # factura arribi a desar-se. Si `instance.save()` falla just després, el
            # número ja queda "cremat" per sempre encara que mai existeixi cap factura
            # amb aquest serie_final -- deixant un forat permanent a la numeració legal
            # (detectat a producció: números reservats que mai es van arribar a
            # desar). Envoltant-ho tot en una única transacció, un `instance.save()`
            # fallit fa rollback també de la reserva del número (nested atomic = savepoint).
            with transaction.atomic():
                instance.serie_final = generate_serie_final(
                    serie.token, date_str,
                    invoice_type=invoice_type,
                    exclude_status_token=status_pending_token,
                    invoice=instance,
                )
                instance.serie_token_final = serie.token

                if generate_verifactu and False:
                    single_batch = False if hasattr(instance, '_bulk_batch') else True
                    create_verifactu_invoice(instance, single_batch=single_batch)

                instance.save()
        else:
            instance.save()

        if genPdf:
            generate_report_invoice_pdf(instance, config_cache=config_cache)
    
    # Handle cancelled status
    # cancel already handled in another signal
    """ if instance.status == status_cancelled:
        payment_status_cancelled = PaymentStatus.objects.get(token=config_values['payment_status_cancelled_token'])
        Payment.objects.filter(invoice=instance).update(status=payment_status_cancelled) """