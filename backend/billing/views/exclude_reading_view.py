import re
from datetime import datetime, timedelta, date
from decimal import Decimal
from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from celery.result import AsyncResult
from billing.models import Reading, ReadingBatch, ReadingBatchStatus
from billing.serializers.invoice_serializer import InvoiceSerializer
from billing.serializers.reading_serializer import ReadingMinimalSerializer
from contract.models import Contract, ContractStatus
from coredata.models import ConfigProject
from service.models import SupplyPoint
from ..utils.reading_service import get_existing_reading
from django.db.models import F, Value, IntegerField, ExpressionWrapper, fields
from django.db.models.functions import Abs


class ExcludeReadingView(views.APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Reading.objects.all().order_by('-created_at')

    def put(self, request):
        try:
            id = request.data.get('id')
            if id is None:
                return Response({"error": "Missing id"}, status=status.HTTP_404_NOT_FOUND)
            reading = Reading.objects.get(id=id)
            pending_status = ReadingBatchStatus.objects.get(is_default=True)
            # Lot d'origen "real": si la lectura ja és dins d'un lot d'excloses
            # (p.ex. es torna a excloure), fem servir el seu origen per evitar
            # cadenes de lots d'excloses (lot exclòs d'un lot exclòs).
            origin_batch = reading.batch.excluded_from if reading.batch.is_excluded else reading.batch
            # Un lot d'excloses per cada lot d'origen: busquem si ja n'hi ha un
            # de pendent per aquest origen concret, en lloc d'agafar qualsevol
            # lot d'excloses pendent.
            batch = ReadingBatch.objects.filter(
                status=pending_status,
                is_excluded=True,
                excluded_from=origin_batch,
            ).first()
            if not batch:
                origin_label = origin_batch.token or str(origin_batch.id)
                # Treiem el prefix "Lectures " del nom del lot original (si en té)
                # per no duplicar la paraula al nom del lot d'excloses.
                origin_display = origin_batch.name or origin_label
                origin_display = re.sub(r'^lectures\s+', '', origin_display, flags=re.IGNORECASE)
                batch = ReadingBatch.objects.create(
                    type=origin_batch.type,
                    token='RBE-' + origin_label,
                    name='Lectures excloses ' + origin_display,
                    processed_at=datetime.now(),
                    status=pending_status,
                    excluded_from=origin_batch,
                    is_excluded=True
                )
            reading.batch = batch
            reading.save()
            return Response({}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"error": f"Unexpected error occurred: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)