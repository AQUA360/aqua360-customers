from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from contract.models import (ContractSurrogation)
from contract.serializers.contract_surrogation_serializer import (ContractSurrogationSerializer)
from contract.permissions import ContractPermission
class ContractSurrogationViewSet(viewsets.ModelViewSet):
    queryset = ContractSurrogation.objects.all().order_by('token')
    serializer_class = ContractSurrogationSerializer
    permission_classes = [IsAuthenticated, ContractPermission]
    search_fields = ['token', 'name']
    ordering_fields = ['token', 'name']