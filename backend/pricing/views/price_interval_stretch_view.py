from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from django_filters.rest_framework import DjangoFilterBackend
from ..filters.price_interval_stretch_filter import PriceIntervalStretchFilter
from ..models import PriceIntervalStretch
from ..serializers.price_interval_stretch_serializer import PriceIntervalStretchSerializer
from pricing.permissions import PriceRatePermission
class PriceIntervalStretchViewSet(viewsets.ModelViewSet):
    queryset = PriceIntervalStretch.objects.all().order_by('stretch')
    serializer_class = PriceIntervalStretchSerializer
    permission_classes = [IsAuthenticated, PriceRatePermission]
    filterset_class = PriceIntervalStretchFilter
    filter_backends = [DjangoFilterBackend]
    ordering_fields = '__all__'
    search_fields = '__all__'