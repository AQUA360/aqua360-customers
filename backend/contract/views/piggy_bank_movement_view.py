from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from contract.permissions import ContractPermission

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from contract.models import (PiggyBankMovement)
from contract.serializers.piggy_bank_movement_serializer import PiggyBankMovementSerializer

class PiggyBankMovementViewSet(viewsets.ModelViewSet):
    queryset = PiggyBankMovement.objects.all().order_by('-amount')
    serializer_class = PiggyBankMovementSerializer
    permission_classes = [IsAuthenticated, ContractPermission]
    #filterset_class = PiggyBankMovementFilter
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    
    