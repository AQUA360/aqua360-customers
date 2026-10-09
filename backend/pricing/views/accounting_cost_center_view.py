from rest_framework import status
from rest_framework.decorators import action
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from billing.permissions import BillingPermission
from pricing.models import (AccountingCostCenter)
from pricing.serializers.accounting_pricing_serializer import AccountingCostCenterSerializer
class AccountingCostCenterViewSet(viewsets.ModelViewSet):
    queryset = AccountingCostCenter.objects.all().order_by('token')
    serializer_class = AccountingCostCenterSerializer
    permission_classes = [IsAuthenticated, BillingPermission]
    
    def get_serializer_class(self):
        return AccountingCostCenterSerializer

    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()