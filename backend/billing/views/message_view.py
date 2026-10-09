from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat

from billing.filter.message_filter import MessageFilter
from billing.models import Message
from billing.serializers.message_serializer import MessageSerializer, MessageMinimalSerializer
from billing.permissions import InvoicePermission
class MessageViewSet(viewsets.ModelViewSet):
  """
  API endpoint that allows reading batches to be viewed or edited.
  """
  queryset = Message.objects.all().filter(is_active=True).order_by('token')
  permission_classes = [IsAuthenticated, InvoicePermission]
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  filterset_class = MessageFilter
  serializer_class = MessageSerializer
  search_fields = ['token','name']
  ordering_fields = ['token','name']

  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context