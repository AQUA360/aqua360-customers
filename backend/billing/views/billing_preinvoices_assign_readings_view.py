# contract/views/contract_request_finalize_view.py

from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django.db.models import Q

from billing.models import Billing, ReadingBatch, Reading
from django.shortcuts import get_object_or_404
from billing.utils.reading_filters import PENDING_READING_FILTER

class BillingPreInvoicesAssignReadingsViewSet(views.APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Billing.objects.all().order_by('-created_at')
    
    def post(self, request, id):
        try:
            if not id:
                return Response({"error": "billing id is required."}, status=status.HTTP_400_BAD_REQUEST)
           
            billing = get_object_or_404(Billing, id=id)
            
            reading_batch_ids = request.data.get('reading_batch_ids')
            if not reading_batch_ids:
                return Response({"num_assigned_readings": 0}, status=status.HTTP_200_OK)
            
            # Get all supply point IDs that belong to routes in this billing using a single query
            # Route -> RoutePosition -> Property -> SupplyPoint
            billing_supply_point_ids = set(
                billing.routes.values_list(
                    'positions__properties__supply_points__id',
                    flat=True
                ).distinct()
            )
            
            # Remove None values in case of null relationships
            billing_supply_point_ids.discard(None)
            
            if not billing_supply_point_ids:
                return Response({"num_assigned_readings": 0}, status=status.HTTP_200_OK)
            
            # Normal readings: matched by supply point on billing routes
            readings_by_sp = Reading.objects.filter(
                batch_id__in=reading_batch_ids,
                supply_point_id__in=billing_supply_point_ids
            ).filter(
                PENDING_READING_FILTER
            )

            # Canonical general-meter readings may have supply_point null; match via meter → SP
            readings_general_canonical = Reading.objects.filter(
                batch_id__in=reading_batch_ids,
                meter__is_general=True,
                copied_from__isnull=True,
                meter__supply_points__id__in=billing_supply_point_ids,
            ).filter(
                PENDING_READING_FILTER
            )

            readings_to_update = (readings_by_sp | readings_general_canonical).distinct()
            
            count = readings_to_update.count()
            if count > 0:
                readings_to_update.update(billing=billing)
            
            response = {"num_assigned_readings": count}

            return Response(response, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
