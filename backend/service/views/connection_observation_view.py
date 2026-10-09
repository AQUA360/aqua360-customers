from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from service.filters.connection_observation_filter import ConnectionObservationFilter
from service.serializers.connection_serializer import ConnectionObservationSerializer

from service.models import (ConnectionObservation )
from service.permissions import ConnectionPermission

class ConnectionObservationViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Property to be viewed or edited.
    """
    queryset = ConnectionObservation.objects.all().filter(is_active=True)
    serializer_class = ConnectionObservationSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = ConnectionObservationFilter
    permission_classes = [IsAuthenticated, ConnectionPermission]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


