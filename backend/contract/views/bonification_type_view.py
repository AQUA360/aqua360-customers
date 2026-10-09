from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from contract.models import BonificationType
from contract.serializers.bonification_type_serializer import BonificationTypeSerializer
from contract.permissions import ContractPermission

class BonificationTypeViewSet(viewsets.ModelViewSet):
    queryset = BonificationType.objects.all().order_by('token')
    serializer_class = BonificationTypeSerializer
    permission_classes = [IsAuthenticated, ContractPermission]
    search_fields = ['token', ]
    ordering_fields = ['token',]
    
    