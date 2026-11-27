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

    def _exploitation_id(self, request):
        raw = request.query_params.get('exploitation') or request.data.get('exploitation')
        if raw in (None, '', []):
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    @action(detail=False, methods=['get', 'put', 'patch'], url_path='current')
    def current(self, request):
        exploitation_id = self._exploitation_id(request)
        config = AccountingConfig.get_for_exploitation(exploitation_id)
        if request.method == 'GET':
            serializer = self.get_serializer(config)
            return Response(serializer.data, status=status.HTTP_200_OK)

        partial = request.method == 'PATCH'
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        if exploitation_id is not None and 'exploitation' not in data and 'exploitation_id' not in data:
            data['exploitation_id'] = exploitation_id
        serializer = self.get_serializer(config, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
