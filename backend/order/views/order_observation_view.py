from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from ..filters.order_observation_filter import OrderObservationFilter
from ..models import OrderObservation
from ..serializers.order_serializer import OrderObservationSerializer
from order.permissions import OrderPermission
class OrderObservationViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Property to be viewed or edited.
    """
    queryset = OrderObservation.objects.all().filter(is_active=True)
    serializer_class = OrderObservationSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = OrderObservationFilter
    permission_classes = [IsAuthenticated, OrderPermission]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)