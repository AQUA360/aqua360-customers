from rest_framework import viewsets,status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from ..models import (VariableCalculation)
from ..serializers.value_objects_serializer import VariableCalculationSerializer
from pricing.permissions import PriceRatePermission
class VariableCalculationViewSet(viewsets.ModelViewSet):
    queryset = VariableCalculation.objects.all().order_by('token')
    serializer_class = VariableCalculationSerializer
    permission_classes = [IsAuthenticated, PriceRatePermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    search_fields = '__all__'
    ordering_fields = '__all__'
    