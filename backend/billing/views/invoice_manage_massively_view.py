import logging

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.filter.invoice_filter import InvoiceFilter
from billing.models import Invoice, Payment, PaymentStatus
from billing.utils.invoice_service import get_invoice_status
from billing.utils.payment_service import (
    check_claim_payments_for_paid_invoice,
    disconnect_payment_signals,
    generate_payment_movement,
    log_invoice_status,
    log_payment_status,
    reconnect_payment_signals,
)
from coredata.models import ConfigProject

logger = logging.getLogger(__name__)

PREVIEW_PAGE_SIZE = 50

# Formes de pagament que es cobren per un altre circuit (remesa, saldo, TPV)
EXCLUDED_PAYMENT_TYPES = ['DIRECT_DEBIT', 'BALANCE', 'TPV_ONLINE']

# Estats de factura que no es poden marcar com a pagats en massa
EXCLUDED_INVOICE_STATUS_TOKENS = [
    'invoice_status_dropped_token',
    'invoice_status_cancelled_token',
    'invoice_status_commitment_token',
    'invoice_status_payoff_token',
    'invoice_status_pending_token',
]

# Cobraments que no s'han de tocar en pagar la factura (ja pagats o anul·lats)
SKIPPED_PAYMENT_STATUS_TOKENS = [
    'payment_status_paid_token',
    'payment_status_cancelled_token',
    'payment_status_payoff_token',
    'payment_status_dropped_token',
]


def _payment_statuses(tokens):
    values = ConfigProject.objects.filter(token__in=tokens).values_list('value', flat=True)
    return list(PaymentStatus.objects.filter(token__in=list(values)))


def _filtered_invoices(data):
    """Factures que mostra la llista amb els mateixos filtres (sense les condicions del pagament)."""
    invoice_type_token = ConfigProject.objects.get(token='invoice_type_invoice_token').value
    queryset = Invoice.objects.filter(
        is_active=True,
        is_excluded=False,
        type__token=invoice_type_token,
    )
    filterset = InvoiceFilter(data, queryset=queryset)
    if not filterset.is_valid():
        return None, filterset.errors
    return filterset.qs, None


def _payable_conditions():
    paid_status = get_invoice_status('invoice_status_paid_token')
    excluded_statuses = [get_invoice_status(token) for token in EXCLUDED_INVOICE_STATUS_TOKENS]
    return paid_status, excluded_statuses


def _payable(queryset, paid_status, excluded_statuses):
    return queryset.exclude(
        status__in=[paid_status, *excluded_statuses]
    ).exclude(
        payment_type_token_final__in=EXCLUDED_PAYMENT_TYPES
    )


def _skipped_summary(queryset, paid_status, excluded_statuses):
    """Quantes factures de la llista queden fora i per quin motiu (cada factura, un sol motiu)."""
    already_paid = queryset.filter(status=paid_status)
    not_payable_status = queryset.filter(status__in=excluded_statuses)
    payment_type = queryset.exclude(
        status__in=[paid_status, *excluded_statuses]
    ).filter(payment_type_token_final__in=EXCLUDED_PAYMENT_TYPES)
    return [
        {'reason': reason, 'count': count}
        for reason, count in (
            ('already_paid', already_paid.count()),
            ('status', not_payable_status.count()),
            ('payment_type', payment_type.count()),
        )
        if count
    ]


def _preview_row(invoice):
    return {
        'id': invoice.id,
        'serie_final': invoice.serie_final,
        'issue_date': invoice.issue_date,
        'customer_final': invoice.customer_final,
        'total_final': invoice.total_final,
        'left_to_pay': invoice.left_to_pay,
        'payment_type_final': invoice.payment_type_final,
        'status_name': invoice.status.name if invoice.status else None,
        'status_color': invoice.status.color if invoice.status else None,
    }


class InvoiceManageMassivelyViewSet(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        filtered, errors = _filtered_invoices(request.data)
        if errors is not None:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        paid_status, excluded_statuses = _payable_conditions()
        invoices = _payable(filtered, paid_status, excluded_statuses).order_by('issue_date', 'id')

        if not request.data.get('saving', False):
            return self.summary(request, filtered, invoices, paid_status, excluded_statuses)
        return self.save(request, invoices, paid_status, excluded_statuses)

    def summary(self, request, filtered, invoices, paid_status, excluded_statuses):
        try:
            page_number = max(int(request.data.get('page') or 1), 1)
        except (TypeError, ValueError):
            page_number = 1
        paginator = Paginator(invoices.select_related('status'), PREVIEW_PAGE_SIZE)
        page = paginator.get_page(page_number)
        total_amount = invoices.aggregate(total=Sum('left_to_pay'))['total'] or 0
        return Response({
            'count': paginator.count,
            'total_amount': total_amount,
            'invoice_ids': list(invoices.values_list('id', flat=True)),
            'skipped': _skipped_summary(filtered, paid_status, excluded_statuses),
            'page': page.number,
            'has_next': page.has_next(),
            'results': [_preview_row(invoice) for invoice in page.object_list],
        })

    def save(self, request, invoices, paid_status, excluded_statuses):
        # Només es paguen les factures que l'usuari ha vist i confirmat; el servidor hi torna a
        # aplicar els filtres i les condicions, de manera que la llista només pot restringir.
        invoice_ids = request.data.get('invoice_ids')
        if not isinstance(invoice_ids, list) or not invoice_ids:
            return Response({'detail': 'invoice_ids és obligatori.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            invoice_ids = [int(invoice_id) for invoice_id in invoice_ids]
        except (TypeError, ValueError):
            return Response({'detail': 'invoice_ids no és vàlid.'}, status=status.HTTP_400_BAD_REQUEST)

        selected_ids = list(invoices.filter(id__in=invoice_ids).values_list('id', flat=True))
        skipped_count = len(set(invoice_ids)) - len(selected_ids)

        user = request.user
        paid_payment_status = PaymentStatus.objects.get(
            token=ConfigProject.objects.get(token='payment_status_paid_token').value
        )
        skipped_payment_statuses = _payment_statuses(SKIPPED_PAYMENT_STATUS_TOKENS)
        today = timezone.now().date()
        updated_count = 0
        error_count = 0

        # Senyals desconnectats: els moviments i les reclamacions es generen a mà
        disconnect_payment_signals()
        try:
            for invoice_id in selected_ids:
                try:
                    with transaction.atomic():
                        invoice = _payable(
                            Invoice.objects.select_for_update().filter(id=invoice_id),
                            paid_status, excluded_statuses,
                        ).first()
                        if invoice is None:
                            # Ha canviat entre la previsualització i la confirmació
                            skipped_count += 1
                            continue
                        self.pay_invoice(invoice, user, today, paid_status, paid_payment_status, skipped_payment_statuses)
                        updated_count += 1
                except Exception:
                    logger.exception('Error marcant com a pagada la factura %s en massa', invoice_id)
                    error_count += 1
        finally:
            reconnect_payment_signals()

        return Response({
            'updated_count': updated_count,
            'skipped_count': skipped_count,
            'error_count': error_count,
        }, status=status.HTTP_200_OK)

    @staticmethod
    def pay_invoice(invoice, user, today, paid_status, paid_payment_status, skipped_payment_statuses):
        payments = Payment.objects.filter(
            invoice=invoice, is_active=True, is_excluded=False,
        ).exclude(status__in=skipped_payment_statuses)
        for payment in payments:
            log_payment_status(payment, paid_payment_status, user, today, payment.payment_type_token)
            generate_payment_movement(
                payment, paid_payment_status,
                today, payment.payment_type_token,
                payment.payment_bank, user,
            )
            payment.status = paid_payment_status
            payment.payment_date = today
            payment.paid_at = today
            payment.save()

        log_invoice_status(invoice, paid_status, user)
        invoice.status = paid_status
        invoice.left_to_pay = 0
        invoice.save()
        check_claim_payments_for_paid_invoice(invoice, user)
