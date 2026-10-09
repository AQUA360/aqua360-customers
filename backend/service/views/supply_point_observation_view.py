from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from service.filters.supply_point_observation_filter import SupplyPointObservationFilter

from service.models import (SupplyPointObservation )
from service.serializers.supply_point_serializer import SupplyPointObservationSerializer
from service.permissions import SupplyPointPermission

class SupplyPointObservationViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Property to be viewed or edited.
    """
    queryset = SupplyPointObservation.objects.all().filter(is_active=True)
    serializer_class = SupplyPointObservationSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = SupplyPointObservationFilter
    permission_classes = [IsAuthenticated, SupplyPointPermission]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


