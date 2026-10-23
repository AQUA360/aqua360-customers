from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from billing.permissions import BillingPermission
from pricing.models import AccountingConfig
from pricing.serializers.accounting_config_serializer import AccountingConfigSerializer


class AccountingConfigViewSet(viewsets.GenericViewSet):
    queryset = AccountingConfig.objects.all().order_by('id')
    serializer_class = AccountingConfigSerializer
    permission_classes = [IsAuthenticated, BillingPermission]
    pagination_class = None

    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()

    @action(detail=False, methods=['get', 'put', 'patch'], url_path='current')
    def current(self, request):
        config = AccountingConfig.get_solo()
        if request.method == 'GET':
            serializer = self.get_serializer(config)
            return Response(serializer.data, status=status.HTTP_200_OK)

        partial = request.method == 'PATCH'
        serializer = self.get_serializer(config, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
