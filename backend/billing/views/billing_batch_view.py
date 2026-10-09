from rest_framework import views, viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from billing.filter.billing_batch_filter import BillingBatchFilter
from billing.models import BillingBatch, ReadingBatch, ReadingBatchStatus
from billing.serializers.billing_batch_serializer import BillingBatchSerializer
from contract.models import Contract, ContractStatus
from coredata.models import ConfigProject
from service.models import Route
from service.serializers.route_serializer import RouteListSerializer
from billing.permissions import BillingPermission
from django.db.models import Count, Sum, Q

class BillingBatchViewSet(viewsets.ModelViewSet):
  """
  API endpoint that allows billing batches to be viewed or edited.
  """
  queryset = BillingBatch.objects.all().filter(is_active=True).order_by('token')
  permission_classes = [IsAuthenticated, BillingPermission]
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  filterset_class = BillingBatchFilter
  search_fields = ['token','name']
  ordering_fields = ['token','name']
  
  def get_serializer_class(self):
    return BillingBatchSerializer
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context