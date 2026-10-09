from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from contract.filters import ContractObservationFilter
from contract.models import (ContractObservation)
from contract.serializers.contract_serializer import (ContractObservationSerializer)
from contract.permissions import ContractPermission
class ContractObservationViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Property to be viewed or edited.
    """
    queryset = ContractObservation.objects.all().filter(is_active=True).order_by('-created_at')
    serializer_class = ContractObservationSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = ContractObservationFilter
    permission_classes = [IsAuthenticated, ContractPermission]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)