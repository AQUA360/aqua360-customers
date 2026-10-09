from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from ..models import BillingConsumption
from ..serializers import BillingConsumptionSerializer

class BillingConsumptionViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = BillingConsumption.objects.all().order_by('-year', '-month')
    serializer_class = BillingConsumptionSerializer
    filterset_fields = ['contract', 'year', 'month']
