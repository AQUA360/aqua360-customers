from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from billing.filter.joined_payment_observation_filter import JoinedPaymentObservationFilter
from billing.permissions import PaymentPermission
from billing.serializers.joined_payment_serializer import JoinedPaymentObservationSerializer

from billing.models import JoinedPaymentObservation


class JoinedPaymentObservationViewSet(viewsets.ModelViewSet):
    queryset = JoinedPaymentObservation.objects.all().filter(is_active=True)
    serializer_class = JoinedPaymentObservationSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = JoinedPaymentObservationFilter
    permission_classes = [IsAuthenticated, PaymentPermission]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


