from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat

from billing.filter.invoice_filter import InvoiceFilter
from contract.permissions import ContractPermission
from coredata.models import CallRegister
from coredata.serializers import CallRegisterSerializer
from coredata.filters.call_register_filter import CallRegisterFilter

class CallRegisterViewSet(viewsets.ModelViewSet):
  queryset = CallRegister.objects.all().order_by('-created_at').filter()
  permission_classes = [IsAuthenticated, ContractPermission]
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  filterset_class = CallRegisterFilter
  search_fields = ['token']
  ordering_fields = ['token']
  
  
  def get_serializer_class(self):
    return CallRegisterSerializer
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context