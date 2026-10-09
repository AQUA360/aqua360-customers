# contract/views/contract_request_finalize_view.py

from datetime import datetime, timedelta, date
from decimal import Decimal
from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from celery.result import AsyncResult

from billing.models import Billing, BillingBatch, BillingBatchStatus, BillingStatus, Invoice, Reading, ReadingBatch, ReadingBatchStatus
from billing.serializers.billing_batch_serializer import BillingBatchProgressSerializer, BillingBatchSerializer

from coredata.models import ConfigProject

from ..tasks import process_billing_batch, process_invoice_documents
from django.db.models.functions import Abs
from billing.permissions import BillingPermission

class BillingBatchRegenerateView(views.APIView):
    permission_classes = [IsAuthenticated, BillingPermission]
    queryset = Billing.objects.all().order_by('-created_at')
    def post(self, request, id):
        try:
            # Factures ja finalitzades per via externa (confirmades/pagades/etc. abans
            # que el lot s'acabi de processar): no s'han de tocar en recalcular/regenerar
            # el lot, ja que suposaria perdre la confirmació/pagament ja fet i tornar a
            # generar-ne una nova per a les mateixes lectures.
            prefactura_token = ConfigProject.objects.get(token='invoice_status_pending_token').value

            # Re-include excluded invoices by moving readings back from excluded billings
            excluded_billings = Billing.objects.filter(excluded_from_id=id)
            for ex_billing in excluded_billings:
                # Move readings back to the main billing
                Reading.objects.filter(billing=ex_billing).update(billing_id=id)
                # Delete invoices from the excluded billing (if any), except finalized ones
                Invoice.objects.filter(billing=ex_billing, status__token=prefactura_token).delete()
                # Finalized invoices survive; reattach them to the main billing before
                # deleting the exclusion sub-billing so they don't end up with billing=NULL
                Invoice.objects.filter(billing=ex_billing).update(billing_id=id)
                # Optionally delete the empty excluded billing
                ex_billing.delete()

            # Només s'esborren les que encara són Pre-factura; les ja finalitzades
            # (i les seves Reading, via type_final='F') queden protegides pel filtre
            # que ja aplica process_billing_batch (billing/tasks.py) en excloure lectures
            # que ja tenen una Invoice generada.
            invoices = Invoice.objects.filter(billing=id, status__token=prefactura_token)
            invoices.delete()

            billing = Billing.objects.get(id=id)

            pending_status_token = ConfigProject.objects.get(token='billing_batch_processing').value
            pending_status = BillingStatus.objects.get(token=pending_status_token)
            
            from billing.models import BillingQueue
            from billing.tasks import process_next_queue_item

            queue_item = BillingQueue.objects.create(
                billing=billing,
                task_type='PRE_INVOICE',
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
            # return Response({}, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            return Response({"error": f"Unexpected error occurred: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)