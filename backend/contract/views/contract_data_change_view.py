from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from contract.models import (ContractDataChange)
from contract.serializers.contract_data_change_serializer import (ContractDataChangeSerializer)
from contract.permissions import ContractPermission
class ContractDataChangeViewSet(viewsets.ModelViewSet):
    queryset = ContractDataChange.objects.all().order_by('token')
    serializer_class = ContractDataChangeSerializer
    permission_classes = [IsAuthenticated, ContractPermission]
    search_fields = ['token', 'name']
    ordering_fields = ['token', 'name']