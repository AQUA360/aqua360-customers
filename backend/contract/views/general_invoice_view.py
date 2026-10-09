from datetime import timedelta
from decimal import Decimal
from rest_framework.decorators import action
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from billing.models import Payment, PaymentStatus
from billing.utils.invoice_service import generate_payment_id
from contract.serializers.general_invoice_serializer import GeneralInvoiceSerializer
from contract.permissions import ContractPermission
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from contract.filters.general_invoice_filter import GeneralInvoiceFilter
from contract.models import GeneralInvoice

class GeneralInvoiceViewSet(viewsets.ModelViewSet):
    queryset = GeneralInvoice.objects.all().order_by('-created_at')
    serializer_class = GeneralInvoiceSerializer
    permission_classes = [IsAuthenticated, ContractPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = GeneralInvoiceFilter