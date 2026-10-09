from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from notification.filters.incident_observation_filter import IncidentObservationFilter
from notification.models import IncidentObservation
from notification.serializers.incident_serializer import IncidentObservationSerializer
from notification.permissions import IncidentPermission

class IncidentObservationViewSet(viewsets.ModelViewSet):
    
    queryset = IncidentObservation.objects.all().filter(is_active=True).order_by('-created_at')
    serializer_class = IncidentObservationSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IncidentObservationFilter
    permission_classes = [IsAuthenticated, IncidentPermission]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)