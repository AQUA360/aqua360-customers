from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.pagination import PageNumberPagination
from rest_framework import viewsets

from ..models import AdjustmentIntervalStretch
from ..serializers.value_objects_serializer import AdjustmentIntervalStretchSerializer
from ..filters.adjustment_interval_stretch_filter import AdjustmentIntervalStretchFilter
from pricing.permissions import PriceRatePermission
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

class AdjustmentIntervalStretchViewSet(viewsets.ModelViewSet):
    queryset = AdjustmentIntervalStretch.objects.all()
    serializer_class = AdjustmentIntervalStretchSerializer
    filterset_class = AdjustmentIntervalStretchFilter
    permission_classes = [IsAuthenticated, PriceRatePermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    ordering_fields = '__all__'
    search_fields = '__all__'
    