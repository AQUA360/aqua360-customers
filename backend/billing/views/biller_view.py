from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat

from billing.filter.invoice_filter import InvoiceFilter
from billing.models import Biller
from billing.permissions import BillingPermission
from billing.serializers.biller_serializer import BillerSerializer, BillerMinimalSerializer

class BillerViewSet(viewsets.ModelViewSet):
  """
  API endpoint that allows reading batches to be viewed or edited.
  """
  queryset = Biller.objects.all().filter()
  permission_classes = [IsAuthenticated, BillingPermission]
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  # filterset_class = InvoiceFilter
  search_fields = ['token','name']
  ordering_fields = ['token','name']
  
  def get_serializer_class(self):
    
    if self.request.method in ['GET']:
        if self.action == 'list':  
            return BillerMinimalSerializer
        elif self.action == 'retrieve':
            return BillerSerializer
    return BillerMinimalSerializer
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context