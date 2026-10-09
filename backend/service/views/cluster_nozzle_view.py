from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated


from service.models import (
    ClusterNozzle,
    SupplyPointPlacement
)
from service.serializers.cluster_nozzle_serializer import (
    ClusterNozzleSaveSerializer,
    ClusterNozzleSerializer
)
from service.filters.cluster_nozzle_filter import ClusterNozzleFilter
from django_filters.rest_framework import DjangoFilterBackend
from service.permissions import ClusterPermission

class ClusterNozzleViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows cluster to be viewed or edited.
    """
    queryset = ClusterNozzle.objects.all().prefetch_related('supply_points__meter', 'supply_points__status', 'supply_points__address').order_by('position')
    # serializer_class = ClusterNozzleSerializer
    permission_classes = [IsAuthenticated, ClusterPermission]
    filterset_class = ClusterNozzleFilter
    filter_backends = [DjangoFilterBackend]
    def get_serializer_class(self):
        if self.request.method in ['GET']:
            return ClusterNozzleSerializer
        return ClusterNozzleSaveSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        supply_point_data = request.data.get('supplyPoint')
        placement = supply_point_data.get('placement') if supply_point_data else None
        if placement:
            try:
                placement = SupplyPointPlacement.objects.get(id=placement)
                request.data['supplyPoint']['placement'] = {
                    'token': placement.id,          # ÉS ID, NO TOKEN, PERÒ ID PER ALGUNA RAÓ NO PASA
                    'name': placement.name
                }
            except Exception as e:
                print(e)
                pass
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = ClusterNozzleSerializer(instance)
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = ClusterNozzleSerializer(instance)
        return Response(read_serializer.data)


