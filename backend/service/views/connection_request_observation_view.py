from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from service.filters.connection_request_observation_filter import ConnectionRequestObservationFilter
from service.serializers.connection_request_serializer import ConnectionRequestObservationSerializer

from service.models import (ConnectionRequestObservation )
from service.permissions import ConnectionRequestPermission

class ConnectionRequestObservationViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Property to be viewed or edited.
    """
    queryset = ConnectionRequestObservation.objects.all().filter(is_active=True)
    serializer_class = ConnectionRequestObservationSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = ConnectionRequestObservationFilter
    permission_classes = [IsAuthenticated, ConnectionRequestPermission]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


