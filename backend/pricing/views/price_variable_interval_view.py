from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from ..models import PriceVariableInterval
from ..serializers.price_variable_interval_serializer import PriceVariableIntervalSerializer
from pricing.permissions import PriceRatePermission
class PriceVariableIntervalViewSet(viewsets.ModelViewSet):
    queryset = PriceVariableInterval.objects.all()
    serializer_class = PriceVariableIntervalSerializer
    permission_classes = [IsAuthenticated, PriceRatePermission]