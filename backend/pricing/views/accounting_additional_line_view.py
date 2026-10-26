from rest_framework import status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from billing.permissions import BillingPermission
from pricing.models import AccountingAdditionalLine
from pricing.serializers.accounting_pricing_serializer import AccountingAdditionalLineSerializer


class AccountingAdditionalLinePagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class AccountingAdditionalLineViewSet(viewsets.ModelViewSet):
    queryset = AccountingAdditionalLine.objects.select_related(
        'accounting_pricing',
        'accounting_concept',
        'accounting_concept__type',
    ).order_by('accounting_pricing__token', 'token', 'name')
    serializer_class = AccountingAdditionalLineSerializer
    permission_classes = [IsAuthenticated, BillingPermission]
    pagination_class = AccountingAdditionalLinePagination
    filterset_fields = ['accounting_pricing', 'is_active']

    def get_queryset(self):
        queryset = super().get_queryset()
        pricing_id = self.request.query_params.get('accounting_pricing')
        if pricing_id:
            queryset = queryset.filter(accounting_pricing_id=pricing_id)
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=str(is_active).lower() in ('1', 'true', 'yes'))
        return queryset

    def get_serializer_class(self):
        return AccountingAdditionalLineSerializer

    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()

    def destroy(self, request, *args, **kwargs):
        """Soft-deactivate instead of hard delete."""
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)
