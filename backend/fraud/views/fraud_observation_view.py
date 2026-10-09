from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from fraud.filters.fraud_observation_filter import FraudObservationFilter
from fraud.models import FraudObservation
from fraud.serializers.fraud_serializer import FraudObservationSerializer
from fraud.permissions import FraudPermission
class FraudObservationViewSet(viewsets.ModelViewSet):
    queryset = FraudObservation.objects.all().filter(is_active=True)
    serializer_class = FraudObservationSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = FraudObservationFilter
    permission_classes = [IsAuthenticated, FraudPermission]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


