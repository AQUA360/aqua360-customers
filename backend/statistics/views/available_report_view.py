from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from celery.result import AsyncResult
from statistics.models import AvailableReport, ReportQueue
from statistics.serializers import AvailableReportSerializer
from statistics.permissions import ReportViewPermission
from statistics.tasks import run_report_task, process_next_report_queue_item, apply_report_queue_action
from customers.queue_utils import QueueTaskRevokeError
from statistics.utils.report_filters import request_payload_as_dict, resolve_filter_labels


class AvailableReportViewSet(viewsets.ModelViewSet):
    queryset = AvailableReport.objects.all().order_by('section__position', 'position', 'name')
    serializer_class = AvailableReportSerializer
    permission_classes = [IsAuthenticated, ReportViewPermission]

    # Endpoint per obtenir la llista d'informes actius agrupats/ordenats per al frontal
    @action(detail=False, methods=['get'], url_path='active-list')
    def active_list(self, request):
        reports = self.queryset.filter(is_active=True)
        serializer = self.get_serializer(reports, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Endpoint genèric per llançar qualsevol informe
    @action(detail=True, methods=['post'], url_path='trigger')
    def trigger(self, request, pk=None):
        report = self.get_object()
        if not report.is_active:
            return Response(
                {"error": "Aquest informe està desactivat actualment."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        print("--- DEBUG TRIGGER START ---")
        print("PK:", pk)
        print("Report Name:", report.name)
        
        # Combinem query_params i request.data preservant valors múltiples
        payload = request_payload_as_dict(request)
        
        print("Final Payload:", payload)
        print("--- DEBUG TRIGGER END ---")
        
        try:
            filters_display = resolve_filter_labels(payload)
        except Exception as e:
            print("Could not resolve filter labels:", e)
            filters_display = []

        # Create a ReportQueue item
        queue_item = ReportQueue.objects.create(
            report=report,
            payload=payload,
            filters_display=filters_display,
            status='pending'
        )
        process_next_report_queue_item()
        queue_item.refresh_from_db()
        
        return Response({
            "queue_item_id": queue_item.id,
            "status": queue_item.status,
            "task_id": queue_item.task_id
        }, status=status.HTTP_202_ACCEPTED)


class ReportQueueListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        running_or_pending = ReportQueue.objects.filter(status__in=['running', 'pending']).order_by('created_at')
        completed_or_failed = ReportQueue.objects.filter(status__in=['completed', 'failed', 'warning']).order_by('-completed_at')[:10]
        
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
                        if res.result and isinstance(res.result, dict):
                            doc_id = res.result.get('document_id')
                            if doc_id:
                                q_item.document_id = doc_id
                        q_item.save(update_fields=['status', 'completed_at', 'processed_items', 'document'])
                        process_next_report_queue_item()
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
                        process_next_report_queue_item()
                    except:
                        pass
                    
            results.append({
                "id": q_item.id,
                "report_id": q_item.report_id,
                "report_name": q_item.report.name if q_item.report else None,
                "status": status_val,
                "task_id": q_item.task_id,
                "error_message": q_item.error_message,
                "created_at": q_item.created_at,
                "started_at": q_item.started_at,
                "completed_at": completed_at,
                "total_items": total_items,
                "processed_items": processed_items,
                "percent": percent,
                "document_id": q_item.document_id,
                "document_name": q_item.document.document_name if q_item.document else None,
                "document_url": q_item.document.location_url if q_item.document and q_item.document.location_url else q_item.document.file.url if q_item.document and q_item.document.file else None,
                "filters": q_item.payload,
                "filters_display": q_item.filters_display,
            })
        return Response(results)


class ReportQueueStatusView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, queue_item_id):
        try:
            q_item = ReportQueue.objects.get(id=queue_item_id)
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
                        if res.result and isinstance(res.result, dict):
                            doc_id = res.result.get('document_id')
                            if doc_id:
                                q_item.document_id = doc_id
                        q_item.save(update_fields=['status', 'completed_at', 'processed_items', 'document'])
                        process_next_report_queue_item()
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
                        process_next_report_queue_item()
                    except:
                        pass
                    
            return Response({
                "id": q_item.id,
                "report_id": q_item.report_id,
                "report_name": q_item.report.name if q_item.report else None,
                "status": status_val,
                "task_id": q_item.task_id,
                "error_message": q_item.error_message,
                "created_at": q_item.created_at,
                "started_at": q_item.started_at,
                "completed_at": completed_at,
                "total_items": total_items,
                "processed_items": processed_items,
                "percent": percent,
                "document_id": q_item.document_id,
                "document_name": q_item.document.document_name if q_item.document else None,
                "document_url": q_item.document.location_url if q_item.document and q_item.document.location_url else q_item.document.file.url if q_item.document and q_item.document.file else None,
                "filters": q_item.payload,
                "filters_display": q_item.filters_display,
            })
        except ReportQueue.DoesNotExist:
            return Response({"error": "Report queue item not found."}, status=status.HTTP_404_NOT_FOUND)


class ReportQueueActionView(APIView):
    """
    Accions manuals sobre un item de la cua d'informes, per als casos en què una
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
            q_item = ReportQueue.objects.get(id=queue_item_id)
        except ReportQueue.DoesNotExist:
            return Response({"error": "Report queue item not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            apply_report_queue_action(q_item, action_name)
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
