# contract/views/contract_request_finalize_view.py

from datetime import datetime, timedelta, date, timezone
from decimal import Decimal
from django.shortcuts import get_object_or_404
from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from celery.result import AsyncResult

from billing.models import Billing, BillingBatch, BillingBatchStatus, BillingStatus, Reading, ReadingBatch, ReadingBatchStatus
from billing.serializers.invoice_serializer import InvoiceSerializer
from billing.serializers.reading_serializer import ReadingMinimalSerializer
from contract.models import Contract, ContractStatus
from coredata.models import ConfigProject
from service.models import Route, SupplyPoint
from ..utils.reading_service import get_existing_reading
from django.db.models import F, Value, IntegerField, ExpressionWrapper, fields
from django.db.models.functions import Abs

class ExcludeBillingView(views.APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Billing.objects.all().order_by('-created_at')
    def post(self, request, *args, **kwargs):
        try:
            print(request.data)
            billing_id = request.data.get('billing_id')
            reading_id = request.data.get('reading_id')
            
            if not billing_id or not reading_id:
                return Response({"error": "Missing route_id or reading_route_id"}, status=status.HTTP_404_NOT_FOUND)
            
            pending_status =BillingStatus.objects.get(is_default=True)
            
            billing = get_object_or_404(Billing, id=billing_id)
            reading = get_object_or_404(Reading, id=reading_id)
            
            excludeBillingQs = Billing.objects.filter(excluded_from=billing)
            
            if not excludeBillingQs.exists():
                excludeBilling = Billing.objects.create(
                    status = pending_status,
                    name = f"EX-{billing.name}",
                    token = f"EXR-{billing.token}",
                    excluded_from = billing,
                    biller = billing.biller,
                    is_excluded = True,
                    is_active= True
                )
                excludeBilling.routes.set(billing.routes.all())
            else:
                excludeBilling = excludeBillingQs.first()
                if billing.biller_id and not excludeBilling.biller_id:
                    excludeBilling.biller = billing.biller
                    excludeBilling.save(update_fields=['biller'])
                if not excludeBilling.routes.exists():
                    excludeBilling.routes.set(billing.routes.all())
                
            reading.billing = excludeBilling
            reading.save()
                
            return Response({}, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            return Response({"error": f"Unexpected error occurred: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    