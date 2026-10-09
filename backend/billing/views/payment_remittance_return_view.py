from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from billing.filter.payment_remittance_return_filter import PaymentRemittanceReturnFilter
from billing.models import PaymentRemittanceReturn
from billing.serializers.payment_remittance_return_serializer import PaymentRemittanceReturnSerializer, PaymentRemittanceReturnListSerializer
from billing.permissions import PaymentPermission


class PaymentRemittanceReturnViewSet(viewsets.ModelViewSet):
    queryset = PaymentRemittanceReturn.objects.all().order_by('-return_date')
    serializer_class = PaymentRemittanceReturnSerializer
    permission_classes = [IsAuthenticated, PaymentPermission]
    filterset_class = PaymentRemittanceReturnFilter
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    search_fields = ['token']
    ordering_fields = ['return_date', 'token', 'created_at', 'returned_by', 'return_date']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return PaymentRemittanceReturnListSerializer
        return PaymentRemittanceReturnSerializer
