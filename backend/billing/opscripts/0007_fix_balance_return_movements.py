import datetime
from django.core.management.color import color_style
from django.db.models import F

from billing.models import Invoice, Payment, PaymentRemittanceReturn, PaymentStatus
from billing.utils.payment_service import generate_payment_movement
from coredata.models import ConfigProject

style = color_style()

def run(dry_run=False):
    try:
        invoice_paid_token = ConfigProject.objects.get(token='invoice_status_paid_token').value
    except ConfigProject.DoesNotExist:
        # BD nova (sense ConfigProject): no hi ha res a corregir.
        return
    return_invoices = Invoice.objects.filter(
        bail__isnull=False,
        status__token=invoice_paid_token,
    )
    try:
        piggy_token = ConfigProject.objects.get(token='payment_status_piggy_token').value
        pending_token = ConfigProject.objects.get(token='payment_status_pending_token').value
        payment_status_piggy = PaymentStatus.objects.get(token=piggy_token)
        payment_status_pending = PaymentStatus.objects.get(token=pending_token)
        balance_payments = Payment.objects.filter(
            invoice__in=return_invoices,
            status__token=piggy_token,
            is_active=True,
        )
        for payment in balance_payments:
            payment.status = payment_status_pending
            generate_payment_movement(
                    payment, payment_status_piggy, 
                    payment.payment_date, "BALANCE", 
                    None, None,
                    None, None
                    )
    except Exception as e:
        print(style.ERROR(f"Failed to update return remittances movements date: {e}"))

