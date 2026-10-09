from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from contract.models import (ContractRepresentative)
from contract.serializers.contract_representative_serializer import (ContractRepresentativeSerializer)
from contract.permissions import ContractRequestPermission
class ContractRepresentativeViewSet(viewsets.ModelViewSet):
    queryset = ContractRepresentative.objects.all().order_by('token')
    serializer_class = ContractRepresentativeSerializer
    permission_classes = [IsAuthenticated, ContractRequestPermission]
    search_fields = ['token', 'name']
    ordering_fields = ['token', 'name']