from celery.result import AsyncResult
from rest_framework import status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from billing.models import Billing, BillingQueue, Invoice
from billing.permissions import BillingPermission


class WinCenExportView(views.APIView):
    permission_classes = [IsAuthenticated, BillingPermission]

    def post(self, request, id):
        try:
            billing = Billing.objects.get(id=id)
        except Billing.DoesNotExist:
            return Response({'error': 'Billing not found'}, status=status.HTTP_404_NOT_FOUND)

        invoice_count = Invoice.objects.filter(
            billing=billing, is_active=True, is_excluded=False
        ).count()
        if invoice_count == 0:
            return Response(
                {'error': 'No invoices found for this billing'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from billing.tasks import process_next_queue_item

        queue_item = BillingQueue.objects.create(
            billing=billing,
            task_type='WINCEN_EXPORT',
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


class WinCenExportStatusView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, queue_item_id):
        try:
            q_item = BillingQueue.objects.get(id=queue_item_id, task_type='WINCEN_EXPORT')
        except BillingQueue.DoesNotExist:
            return Response({'error': 'Queue item not found'}, status=status.HTTP_404_NOT_FOUND)

        percent = round((q_item.processed_items / q_item.total_items) * 100, 2) if q_item.total_items > 0 else 0.0
        current = q_item.processed_items
        total = q_item.total_items
        state = q_item.status
        file_url = q_item.file_url

        if q_item.status == 'running' and q_item.task_id:
            res = AsyncResult(q_item.task_id)
            if res.state == 'PROGRESS' and res.info:
                current = res.info.get('current', 0)
                total = res.info.get('total', 0)
                percent = round((current / total) * 100, 2) if total > 0 else 0.0
            elif res.state == 'SUCCESS':
                state = 'completed'
                percent = 100.0

        return Response({
            'queue_item_id': q_item.id,
            'task_id': q_item.task_id,
            'billing_id': q_item.billing_id,
            'status': state,
            'current': current,
            'total': total,
            'percent': percent,
            'file_url': file_url,
        })
