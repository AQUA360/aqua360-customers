from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from communication.filters.communication_observation_filter import CommunicationObservationFilter
from communication.models import CommunicationObservation
from communication.serializers.communication_serializer import CommunicationObservationSerializer
from communication.permissions import CommunicationPermission
class CommunicationObservationViewSet(viewsets.ModelViewSet):
    
    queryset = CommunicationObservation.objects.all().filter(is_active=True).order_by('-created_at')
    serializer_class = CommunicationObservationSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = CommunicationObservationFilter
    permission_classes = [IsAuthenticated, CommunicationPermission]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user) 

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)