from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from contract.filters import ContractRequestObservationFilter
from contract.models import (ContractRequestObservation)
from contract.serializers.contract_request_serializer import (ContractRequestObservationSerializer)
from contract.permissions import ContractRequestPermission
class ContractRequestObservationViewSet(viewsets.ModelViewSet):
    queryset = ContractRequestObservation.objects.all().filter(is_active=True)
    serializer_class = ContractRequestObservationSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = ContractRequestObservationFilter
    permission_classes = [IsAuthenticated, ContractRequestPermission]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)