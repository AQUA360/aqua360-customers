from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat

#from billing.filter import MessageConditionFilter
from billing.models import MessageCondition
from billing.serializers.message_condition_serializer import MessageConditionSerializer
from billing.permissions import InvoicePermission
class MessageConditionViewSet(viewsets.ModelViewSet):
  queryset = MessageCondition.objects.all().filter()
  permission_classes = [IsAuthenticated, InvoicePermission]
  serializer_class = MessageConditionSerializer
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  search_fields = ['token','name']
  ordering_fields = ['token','name']
  
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context