# contract/views/contract_request_finalize_view.py

from datetime import datetime, timedelta, date
from decimal import Decimal
import uuid
from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from celery.result import AsyncResult

from billing.models import Billing, BillingBatch, BillingBatchStatus, BillingStatus, Reading, ReadingBatch, ReadingBatchStatus, BillingQueue
from billing.serializers.billing_batch_serializer import BillingBatchProgressSerializer, BillingBatchSerializer

from coredata.models import ConfigProject
from notification.models import Notification

from ..tasks import process_billing_batch, process_invoice_documents, process_next_queue_item, apply_billing_queue_action
from customers.queue_utils import QueueTaskRevokeError
from django.conf import settings
from django.db.models.functions import Abs
from django.utils import translation
from django.utils.translation import gettext as _
from billing.permissions import BillingPermission

class BillingQueueListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        billing_id = request.query_params.get('billing_id')

        base_qs = BillingQueue.objects.all()
        if billing_id:
            # Quan es demana per un lot concret, no aplicar el límit dels últims 10
            # globals (si no, un item failed/skipped d'aquest lot pot quedar fora de la
            # finestra si hi ha molts altres lots finalitzats recentment al sistema).
            base_qs = base_qs.filter(billing_id=billing_id)

        running_or_pending = base_qs.filter(status__in=['running', 'pending']).order_by('created_at')
        completed_or_failed_qs = base_qs.filter(status__in=['completed', 'failed', 'skipped']).order_by('-completed_at')
        completed_or_failed = completed_or_failed_qs if billing_id else completed_or_failed_qs[:10]

        results = []
        for q_item in list(running_or_pending) + list(completed_or_failed):
            percent = round((q_item.processed_items / q_item.total_items) * 100, 2) if q_item.total_items > 0 else 0.0
            total_items = q_item.total_items
            processed_items = q_item.processed_items
            status_val = q_item.status
            completed_at = q_item.completed_at
            
            if q_item.status == 'running' and q_item.task_id:
                res = AsyncResult(q_item.task_id)
                if res.state == 'PROGRESS' and res.info:
                    processed_items = res.info.get('current', 0)
                    total_items = res.info.get('total', 0)
                    percent = float(res.info.get('percent', 0.0))
                elif res.state == 'SUCCESS':
                    percent = 100.0
                    processed_items = total_items
                    status_val = 'completed'
                    from django.utils import timezone
                    completed_at = timezone.now()
                    try:
                        q_item.status = 'completed'
                        q_item.completed_at = completed_at
                        q_item.processed_items = total_items
                        q_item.save(update_fields=['status', 'completed_at', 'processed_items'])
                        process_next_queue_item()
                    except:
                        pass
                elif res.state in ('FAILURE', 'REVOKED'):
                    status_val = 'failed'
                    from django.utils import timezone
                    completed_at = timezone.now()
                    try:
                        q_item.status = 'failed'
                        q_item.completed_at = completed_at
                        q_item.error_message = str(res.info) if res.state == 'FAILURE' else 'Tasca aturada (revoked).'
                        q_item.save(update_fields=['status', 'completed_at', 'error_message'])
                        process_next_queue_item()
                    except:
                        pass

            results.append({
                "id": q_item.id,
                "billing_id": q_item.billing_id,
                "billing_name": q_item.billing.name if q_item.billing else None,
                "task_type": q_item.task_type,
                "task_type_display": q_item.get_task_type_display(),
                "status": status_val,
                "task_id": q_item.task_id,
                "error_message": q_item.error_message,
                "created_at": q_item.created_at,
                "started_at": q_item.started_at,
                "completed_at": completed_at,
                "total_items": total_items,
                "processed_items": processed_items,
                "invoices_processed": q_item.invoices_processed,
                "documents_generated": q_item.documents_generated,
                "percent": percent
            })
        return Response(results)

class BillingQueueStatusView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, queue_item_id):
        try:
            q_item = BillingQueue.objects.get(id=queue_item_id)
            percent = round((q_item.processed_items / q_item.total_items) * 100, 2) if q_item.total_items > 0 else 0.0
            total_items = q_item.total_items
            processed_items = q_item.processed_items
            status_val = q_item.status
            completed_at = q_item.completed_at
            
            if q_item.status == 'running' and q_item.task_id:
                res = AsyncResult(q_item.task_id)
                if res.state == 'PROGRESS' and res.info:
                    processed_items = res.info.get('current', 0)
                    total_items = res.info.get('total', 0)
                    percent = float(res.info.get('percent', 0.0))
                elif res.state == 'SUCCESS':
                    percent = 100.0
                    processed_items = total_items
                    status_val = 'completed'
                    from django.utils import timezone
                    completed_at = timezone.now()
                    try:
                        q_item.status = 'completed'
                        q_item.completed_at = completed_at
                        q_item.processed_items = total_items
                        q_item.save(update_fields=['status', 'completed_at', 'processed_items'])
                        process_next_queue_item()
                    except:
                        pass
                elif res.state == 'FAILURE':
                    status_val = 'failed'
                    from django.utils import timezone
                    completed_at = timezone.now()
                    try:
                        q_item.status = 'failed'
                        q_item.completed_at = completed_at
                        q_item.error_message = str(res.info)
                        q_item.save(update_fields=['status', 'completed_at', 'error_message'])
                        process_next_queue_item()
                    except:
                        pass
                    
            return Response({
                "id": q_item.id,
                "billing_id": q_item.billing_id,
                "billing_name": q_item.billing.name if q_item.billing else None,
                "task_type": q_item.task_type,
                "task_type_display": q_item.get_task_type_display(),
                "status": status_val,
                "task_id": q_item.task_id,
                "error_message": q_item.error_message,
                "created_at": q_item.created_at,
                "started_at": q_item.started_at,
                "completed_at": completed_at,
                "total_items": total_items,
                "processed_items": processed_items,
                "invoices_processed": q_item.invoices_processed,
                "documents_generated": q_item.documents_generated,
                "percent": percent
            })
        except BillingQueue.DoesNotExist:
            return Response({"error": "Queue item not found."}, status=status.HTTP_404_NOT_FOUND)


class BillingQueueActionView(APIView):
    """
    Accions manuals sobre un item de la cua de facturació, per als casos en què una
    tasca de Celery es queda penjada (kill/skip/restart).
    Body esperat: {"action": "kill" | "skip" | "restart"}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, queue_item_id):
        action_name = request.data.get('action')
        if action_name not in ('kill', 'skip', 'restart'):
            return Response(
                {"error": "Acció no vàlida. Ha de ser 'kill', 'skip' o 'restart'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            q_item = BillingQueue.objects.get(id=queue_item_id)
        except BillingQueue.DoesNotExist:
            return Response({"error": "Queue item not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            apply_billing_queue_action(q_item, action_name)
        except QueueTaskRevokeError as e:
            return Response(
                {"error": f"No s'ha pogut aturar la tasca a Celery; la cua no s'ha modificat. {e}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        q_item.refresh_from_db()

        return Response({
            "id": q_item.id,
            "status": q_item.status,
            "task_id": q_item.task_id,
            "error_message": q_item.error_message,
        }, status=status.HTTP_200_OK)


class BillingBatchSummaryView(views.APIView):
    permission_classes = [IsAuthenticated, BillingPermission]
    queryset = Billing.objects.all().order_by('-created_at')
    def post(self, request):
        try:
            print("NEW BILLING")
            
            billing_id = request.data.get('billing')

            billing = Billing.objects.get(id=billing_id)
            
            pending_status_token = ConfigProject.objects.get(token='billing_batch_processing').value
            pending_status = BillingStatus.objects.get(token=pending_status_token)

            # Create a queue item
            queue_item = BillingQueue.objects.create(
                billing=billing,
                task_type='PRE_INVOICE',
                status='pending'
            )
            process_next_queue_item()
            queue_item.refresh_from_db()

            with translation.override(settings.LANGUAGE_CODE):
                notification_save = {
                    'token': uuid.uuid4().hex,
                    'name': _("Billing pending confirmation"),
                    'description': _("Billing %(name)s pending confirmation") % {"name": billing.name},
                    'module': 'billing',
                    'entity': 'billing',
                    'object_id': billing.id,
                    'is_active': True
                }

            notification = Notification.objects.create(**notification_save)
            
            billing.task_id = queue_item.task_id if queue_item.task_id else ""
            billing.status = pending_status
            billing.save()
            
            return Response({
                "queue_item_id": queue_item.id,
                "status": queue_item.status,
                "task_id": queue_item.task_id
            }, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            return Response({"error": f"Unexpected error occurred: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    def get(self, request):
        try:
            # Validar les dades rebudes
            print('BATCH ID')
            batch_id = request.query_params.get('batch_id')
            if not batch_id:
                return Response({"error": "Batch ID is required."}, status=status.HTTP_400_BAD_REQUEST)
            
            batch = BillingBatch.objects.get(id=batch_id)
            
            result = AsyncResult(batch.task_id)
            
            if result.state == 'SUCCESS':
                response = BillingBatchProgressSerializer(batch).data
            else:
                response = BillingBatchSerializer(batch).data
            
            return Response(response, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Unexpected error occurred: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def serialize_decimal(value):
    """Recursively converts Decimal values to float or str."""
    if isinstance(value, Decimal):
        return float(value)  # or str(value) if you want to keep precision as a string
    elif isinstance(value, dict):
        return {key: serialize_decimal(val) for key, val in value.items()}
    elif isinstance(value, list):
        return [serialize_decimal(item) for item in value]
    return value
        
class TaskProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        task_result = AsyncResult(task_id)
        if task_result.state == 'FAILURE':
            response = {'state': task_result.state, 'error': str(task_result.info)}
        elif task_result.state == 'SUCCESS':
            response = {
                'state': task_result.state,
                'percent': 100,
                'current': len(task_result.result) if isinstance(task_result.result, list) else 1,
                'total': len(task_result.result) if isinstance(task_result.result, list) else 1,
                'result': task_result.result
            }
        elif task_result.info:
            response = {
                'state': task_result.state,
                'percent': serialize_decimal(task_result.info.get('percent', 0)),
                'current': serialize_decimal(task_result.info.get('current', 0)),
                'total': serialize_decimal(task_result.info.get('total', 0)),
            }
        else:
            response = {
                'state': 'UNKNOWN'
            }
        return Response(response)

class BillingBatchDocumentsView(views.APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Billing.objects.all()
    
    def put(self, request, billing_id):
        try:
            print("Generate files")
            
            if not billing_id:
                return Response({"error": "Billing required."}, status=status.HTTP_400_BAD_REQUEST)
            
            print(request.data)
            issue_date = request.data.get('issue_date') if 'issue_date' in request.data else None
            end_date = request.data.get('end_date') if 'end_date' in request.data else None
            send_at = request.data.get('send_date') if 'send_date' in request.data else None
            
            billing = Billing.objects.get(id=billing_id)
            
            if not billing:
                return Response({"error": "Billing not found."}, status=status.HTTP_404_NOT_FOUND)

            invoice_ids = list(
                billing.invoices.filter(is_active=True, is_excluded=False).values_list('id', flat=True)
            )

            pending_status_token = ConfigProject.objects.get(token='billing_batch_processing_documents').value
            pending_status = BillingStatus.objects.get(token=pending_status_token)
            
            print(request)
            context = {'base_url': f"https://{request.get_host()}"}
            
            # Create a queue item
            queue_item = BillingQueue.objects.create(
                billing=billing,
                task_type='DEFINITIVE_INVOICE',
                payload={
                    'invoice_ids': invoice_ids,
                    'context': context,
                    'issue_date': issue_date,
                    'end_date': end_date,
                    'send_at': send_at
                },
                status='pending'
            )
            process_next_queue_item()
            queue_item.refresh_from_db()

            billing.task_id = queue_item.task_id if queue_item.task_id else ""
            billing.status = pending_status
            billing.save()
            
            return Response({
                "queue_item_id": queue_item.id,
                "status": queue_item.status,
                "task_id": queue_item.task_id
            }, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            return Response({"error": f"Unexpected error occurred: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)