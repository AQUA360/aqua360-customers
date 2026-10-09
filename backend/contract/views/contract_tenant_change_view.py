from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from contract.models import (ContractTenantChange)
from contract.serializers.contract_tenant_change_serializer import (ContractTenantChangeSerializer)
from contract.permissions import ContractPermission
class ContractTenantChangeViewSet(viewsets.ModelViewSet):
    queryset = ContractTenantChange.objects.all().order_by('token')
    serializer_class = ContractTenantChangeSerializer
    permission_classes = [IsAuthenticated, ContractPermission]
    search_fields = ['token', 'name']
    ordering_fields = ['token', 'name']