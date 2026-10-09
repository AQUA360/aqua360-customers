from rest_framework import viewsets,status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from ..models import (BillingPeriod)
from ..serializers.value_objects_serializer import BillingPeriodSerializer
from pricing.permissions import PriceRatePermission
class BillingPeriodViewSet(viewsets.ModelViewSet):
    queryset = BillingPeriod.objects.all().order_by('token')
    serializer_class = BillingPeriodSerializer
    permission_classes = [IsAuthenticated, PriceRatePermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    search_fields = '__all__'
    ordering_fields = '__all__'
    