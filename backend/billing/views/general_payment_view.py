from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from billing.models import GeneralPayment, GeneralPaymentMandateLog
from billing.serializers.general_payment_serializer import GeneralPaymentMandateLogSerializer, GeneralPaymentSerializer
from billing.permissions import GeneralPaymentPermission

class GeneralPaymentViewSet(viewsets.ModelViewSet):
    queryset = GeneralPayment.objects.all().order_by('token')
    serializer_class = GeneralPaymentSerializer
    permission_classes = [IsAuthenticated, GeneralPaymentPermission]
    search_fields = ['token', 'name']
    ordering_fields = ['token', 'name']

class GeneralPaymentMandateLogViewSet(viewsets.ModelViewSet):
    queryset = GeneralPaymentMandateLog.objects.all().order_by('-created_at')
    serializer_class = GeneralPaymentMandateLogSerializer
    permission_classes = [IsAuthenticated, GeneralPaymentPermission]
    search_fields = ['general_payment__token', 'general_payment__name']
    ordering_fields = ['-created_at']