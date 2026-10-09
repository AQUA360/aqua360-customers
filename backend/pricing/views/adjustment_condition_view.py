from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from ..models import AdjustmentCondition
from ..serializers.adjustment_serializer import AdjustmentConditionSerializer
from pricing.permissions import PriceRatePermission
class AdjustmentConditionViewSet(viewsets.ModelViewSet):
    queryset = AdjustmentCondition.objects.all()
    serializer_class = AdjustmentConditionSerializer
    permission_classes = [IsAuthenticated, PriceRatePermission]
