from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from django_filters.rest_framework import DjangoFilterBackend
from ..filters.price_variable_interval_stretch_filter import PriceVariableIntervalStretchFilter
from ..models import PriceVariableIntervalStretch
from ..serializers.price_variable_interval_stretch_serializer import PriceVariableIntervalStretchSerializer
from pricing.permissions import PriceRatePermission
class PriceVariableIntervalStretchViewSet(viewsets.ModelViewSet):
    queryset = PriceVariableIntervalStretch.objects.all().order_by('stretch')
    serializer_class = PriceVariableIntervalStretchSerializer
    permission_classes = [IsAuthenticated, PriceRatePermission]
    filterset_class = PriceVariableIntervalStretchFilter
    filter_backends = [DjangoFilterBackend]
    ordering_fields = '__all__'
    search_fields = '__all__'