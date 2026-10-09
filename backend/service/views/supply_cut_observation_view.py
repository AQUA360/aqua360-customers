from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from service.filters.supply_cut_observation_filter import SupplyCutObservationFilter
from service.serializers.supply_cut_serializer import SupplyCutObservationSerializer

from service.models import (SupplyCutObservation )
from service.permissions import SupplyCutPermission

class SupplyCutObservationViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Property to be viewed or edited.
    """
    queryset = SupplyCutObservation.objects.all().filter(is_active=True)
    serializer_class = SupplyCutObservationSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = SupplyCutObservationFilter
    permission_classes = [IsAuthenticated, SupplyCutPermission]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

