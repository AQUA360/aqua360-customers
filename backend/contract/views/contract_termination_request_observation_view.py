from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from contract.filters import ContractTerminationRequestObservationFilter
from contract.models import (ContractTerminationRequestObservation)
from contract.serializers.contract_termination_request_serializer import (ContractTerminationRequestObservationSerializer)
from contract.permissions import ContractTerminationRequestPermission
class ContractTerminationRequestObservationViewSet(viewsets.ModelViewSet):
    queryset = ContractTerminationRequestObservation.objects.all().filter(is_active=True)
    serializer_class = ContractTerminationRequestObservationSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = ContractTerminationRequestObservationFilter
    permission_classes = [IsAuthenticated, ContractTerminationRequestPermission]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)