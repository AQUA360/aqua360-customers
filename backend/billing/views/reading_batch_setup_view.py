from rest_framework import status
from rest_framework.decorators import action
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Prefetch

from billing.models import ReadingBatch, Reading
from billing.serializers.reading_serializer import ReadingSerializer
from coredata.models import ConfigProject
from service.models import SupplyPoint
from billing.utils.reading_batch_service import (
    SETUP_FILTERS,
    get_setup_filter_supply_point_ids,
)
from service.serializers.supply_point_serializer import SupplyPointContractsSerializer, SupplyPointMinimalContractsSerializer, SupplyPointMinimalSerializer
from billing.permissions import ReadingPermission

class ReadingBatchSetupViewSet(viewsets.ViewSet):

    permission_classes = [IsAuthenticated, ReadingPermission]
    lookup_field = 'id'
    queryset = ReadingBatch.objects.all().order_by('-created_at')
    
    def retrieve(self, request, id=None):
        try:
            # Optimize the initial query
            reading_batch = ReadingBatch.objects.select_related('status').prefetch_related(
                'routes',
                'readings',
                'documents__readings',
                'fix_meters'
            ).get(id=id)
            
            filter = request.query_params.get('readings')
            search = request.query_params.get('search')
            active_contract = ConfigProject.objects.get(token='contract_active_token').value
            
            response = []
            
            def apply_search(qs):
                if search:
                    from django.db.models import Q
                    return qs.filter(
                        Q(contracts__token__icontains=search) |
                        Q(contracts__holder__name__icontains=search) |
                        Q(address__address_search__icontains=search)
                    ).distinct()
                return qs

            if filter in SETUP_FILTERS:
                supply_point_ids = get_setup_filter_supply_point_ids(
                    reading_batch, filter, active_contract
                )
                if not supply_point_ids:
                    return Response({
                        'count': 0,
                        'next': None,
                        'previous': None,
                        'results': []
                    })

                supply_points = SupplyPoint.objects.select_related(
                    'type', 'status', 'property__route_position__route'
                ).filter(id__in=supply_point_ids).order_by('id')
                supply_points = apply_search(supply_points)

                paginator = PageNumberPagination()
                paginator.page_size = 30  # Default page size, can be overridden with ?page_size=XX
                paginated_queryset = paginator.paginate_queryset(supply_points, request)

                if filter == 'extra':
                    # Valor de la lectura del fitxer per a cada supply point sobrant
                    page_ids = [sp.id for sp in paginated_queryset]
                    readings_objects = {
                        reading.supply_point_id: reading
                        for reading in Reading.objects.filter(
                            document__batch=reading_batch,
                            is_control=False,
                            supply_point_id__in=page_ids,
                        )
                    }
                    serialized_supply_points = SupplyPointMinimalSerializer(paginated_queryset, many=True).data
                    response = [{
                        'id': sp['id'],
                        'token': sp['token'],
                        'address': sp['address_complete'],
                        'reading_value': readings_objects.get(sp['id']).reading_value if readings_objects.get(sp['id']) else None
                    } for sp in serialized_supply_points]
                else:
                    response = SupplyPointMinimalContractsSerializer(paginated_queryset, many=True).data

                return paginator.get_paginated_response(response)

            print(reading_batch)
            
            return Response({
                'status': 'ok',
                'data': response,
                'count': len(response)
            })
            
        except ReadingBatch.DoesNotExist:
            return Response(
                {"error": "el lot de lectura no existeix"},
                status=status.HTTP_404_NOT_FOUND
            )
