from celery.result import AsyncResult
from rest_framework import status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from billing.models import Billing, BillingQueue, Invoice
from billing.permissions import BillingPermission


class BillingRegeneratePDFsView(views.APIView):
    permission_classes = [IsAuthenticated, BillingPermission]

    def post(self, request, id):
        try:
            billing = Billing.objects.get(id=id)
        except Billing.DoesNotExist:
            return Response({'error': 'Billing not found'}, status=status.HTTP_404_NOT_FOUND)

        invoice_count = Invoice.objects.filter(billing=billing, is_active=True).count()
        if invoice_count == 0:
            return Response({'error': 'No invoices found for this billing'}, status=status.HTTP_400_BAD_REQUEST)

        from billing.tasks import process_next_queue_item

        queue_item = BillingQueue.objects.create(
            billing=billing,
            task_type='REGENERATE_PDFS',
            status='pending',
            total_items=invoice_count,
        )
        process_next_queue_item()
        queue_item.refresh_from_db()

        return Response({
            'queue_item_id': queue_item.id,
            'task_id': queue_item.task_id,
            'billing_id': billing.id,
            'total': invoice_count,
            'status': queue_item.status,
        }, status=status.HTTP_202_ACCEPTED)


class BillingRegeneratePDFsStatusView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        res = AsyncResult(task_id)

        if res.state == 'PROGRESS' and res.info:
            current = res.info.get('current', 0)
            total = res.info.get('total', 0)
            percent = round((current / total) * 100, 2) if total > 0 else 0.0
        elif res.state == 'SUCCESS':
            result = res.result or {}
            current = result.get('generated', 0)
            total = result.get('total', 0)
            percent = 100.0
        else:
            current = 0
            total = 0
            percent = 0.0

        return Response({
            'task_id': task_id,
            'state': res.state,
            'current': current,
            'total': total,
            'percent': percent,
        })
