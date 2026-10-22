from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone

from billing.models import Invoice, InvoiceStatus, Payment, PaymentStatus
from billing.filter.invoice_filter import InvoiceFilter
from coredata.models import ConfigProject
from billing.utils.payment_service import generate_payment_movement, log_payment_status, log_invoice_status, disconnect_payment_signals, reconnect_payment_signals
from billing.utils.invoice_service import get_invoice_status

class InvoiceManageMassivelyViewSet(APIView):
    permission_classes = [IsAuthenticated]
  
    def post(self, request, *args, **kwargs):
        # We use InvoiceFilter to apply the same logic as the list view
        invoice_type_invoice_token = ConfigProject.objects.get(token='invoice_type_invoice_token').value
        queryset = Invoice.objects.filter(type_final=invoice_type_invoice_token)
        filterset = InvoiceFilter(request.data, queryset=queryset)
        
        if not filterset.is_valid():
            return Response(filterset.errors, status=status.HTTP_400_BAD_REQUEST)
            
        invoices = filterset.qs.distinct()
        
        paid_invoice_status = get_invoice_status("invoice_status_paid_token")
        invoice_status_dropped = get_invoice_status("invoice_status_dropped_token")
        invoice_status_cancelled = get_invoice_status("invoice_status_cancelled_token")
        invoice_status_commitment = get_invoice_status("invoice_status_commitment_token")
        invoice_status_payoff = get_invoice_status("invoice_status_payoff_token")
        invoices = invoices.exclude(
            status__in=[paid_invoice_status, invoice_status_dropped, invoice_status_cancelled, invoice_status_commitment, invoice_status_payoff]
            ).exclude(
            payment_type_token_final__in=['DIRECT_DEBIT', 'BALANCE', 'TPV_ONLINE']
        )
            
        unique_statuses = invoices.values_list('status__name', flat=True).distinct()
        
        is_saving = request.data.get('saving', True)
        
        if not is_saving:
            # Summary mode: return counts and totals
            total_amount = sum(invoice.total_final for invoice in invoices if invoice.total_final)
            return Response({
                'count': invoices.count(),
                'total_amount': total_amount,
                'invoice_ids': list(invoices.values_list('id', flat=True))
            })
            
        # Saving mode: update invoices to paid
        user = request.user
        paid_invoice_status = get_invoice_status("invoice_status_paid_token")
        paid_payment_status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)
        
        updated_count = 0
        now = timezone.now()
        
        # Disconnect signals to handle things manually and avoid performance issues/loops
        disconnect_payment_signals()
        
        try:
            with transaction.atomic():
                for invoice in invoices:
                    if invoice.status == paid_invoice_status:
                        continue
                        
                    # Mark payments as paid
                    payments = Payment.objects.filter(invoice=invoice)
                    for payment in payments:
                        if payment.status != paid_payment_status:
                            # Log payment status change
                            log_payment_status(payment, paid_payment_status, user, now.date(), payment.payment_type_token)
                            
                            # Generate movement
                            generate_payment_movement(
                                payment, paid_payment_status, 
                                now.date(), payment.payment_type_token, 
                                payment.payment_bank, user
                            )
                            
                            payment.status = paid_payment_status
                            payment.payment_date = now.date()
                            payment.paid_at = now.date()
                            payment.save()
                    
                    # Mark invoice as paid
                    log_invoice_status(invoice, paid_invoice_status, user)
                    invoice.status = paid_invoice_status
                    invoice.left_to_pay = 0
                    invoice.save()
                    updated_count += 1
        finally:
            reconnect_payment_signals()
            
        return Response({
            'message': f'Successfully updated {updated_count} invoices to Paid',
            'updated_count': updated_count
        }, status=status.HTTP_200_OK)
