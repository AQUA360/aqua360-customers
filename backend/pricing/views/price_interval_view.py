from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from ..models import PriceInterval
from ..serializers.price_interval_serializer import PriceIntervalSerializer
from pricing.permissions import PriceRatePermission
class PriceIntervalViewSet(viewsets.ModelViewSet):
    queryset = PriceInterval.objects.all()
    serializer_class = PriceIntervalSerializer
    permission_classes = [IsAuthenticated, PriceRatePermission]