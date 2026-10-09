from rest_framework import views, viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from billing.models import EstimatedBag
from billing.serializers.estimated_bag_serializer import EstimatedBagSerializer
from contract.permissions import ContractPermission
class EstimatedBagViewSet(viewsets.ModelViewSet):
  queryset = EstimatedBag.objects.all().filter(is_active=True).order_by('total_consumption','token')
  permission_classes = [IsAuthenticated, ContractPermission]
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  search_fields = ['token','name']
  ordering_fields = ['token','name']
  
  def get_serializer_class(self):
    return EstimatedBagSerializer
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context