from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from contract.models import (ContractPayment)
from contract.serializers.contract_payment_serializer import (ContractPaymentSerializer)
from contract.permissions import ContractPermission
class ContractPaymentViewSet(viewsets.ModelViewSet):
    queryset = ContractPayment.objects.all().order_by('token')
    serializer_class = ContractPaymentSerializer
    permission_classes = [IsAuthenticated, ContractPermission]
    search_fields = ['token', 'name']
    ordering_fields = ['token', 'name']