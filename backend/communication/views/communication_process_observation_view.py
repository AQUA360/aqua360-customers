from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from communication.filters.communication_process_observation_filter import CommunicationProcessObservationFilter
from communication.models import CommunicationProcessObservation
from communication.serializers.communication_process_serializer import CommunicationProcessObservationSerializer
from communication.permissions import CommunicationPermission
class CommunicationProcessObservationViewSet(viewsets.ModelViewSet):
    
    queryset = CommunicationProcessObservation.objects.all().filter(is_active=True).order_by('-created_at')
    serializer_class = CommunicationProcessObservationSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = CommunicationProcessObservationFilter
    permission_classes = [IsAuthenticated, CommunicationPermission]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)