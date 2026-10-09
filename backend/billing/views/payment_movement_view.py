from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat

from billing.filter.payment_movement_filter import PaymentMovementFilter
from billing.models import PaymentMovement
from billing.permissions import InvoicePermission
from billing.serializers.payment_movement_serializer import PaymentMovementSerializer

class PaymentMovementViewSet(viewsets.ModelViewSet):
  queryset = PaymentMovement.objects.all().filter(is_active=True).order_by('-movement_date','-timestamp')
  permission_classes = [IsAuthenticated, InvoicePermission]
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  filterset_class = PaymentMovementFilter
  serializer_class = PaymentMovementSerializer

  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context