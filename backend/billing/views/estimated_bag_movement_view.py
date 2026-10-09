from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions


from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from ..models import (EstimatedBagMovement)
from ..serializers.estimated_bag_movement_serializer import EstimatedBagMovementSerializer
from contract.permissions import ContractPermission
class EstimatedBagMovementViewSet(viewsets.ModelViewSet):
    queryset = EstimatedBagMovement.objects.all().order_by('-movement_date', '-created_at')
    serializer_class = EstimatedBagMovementSerializer
    permission_classes = [IsAuthenticated, ContractPermission]
    #filterset_class = EstimatedBagMovementFilter
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    
    