from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat

from communication.models import MessageTypeTemplate
from communication.filters.message_type_template_filter import MessageTypeTemplateFilter
from communication.serializers.value_objects_serializer import MessageTypeTemplateSerializer
from communication.permissions import CommunicationPermission
class MessageTypeTemplateViewSet(viewsets.ModelViewSet):
  queryset = MessageTypeTemplate.objects.all().filter().order_by('-created_at')
  permission_classes = [IsAuthenticated, CommunicationPermission]
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  filterset_class = MessageTypeTemplateFilter
  serializer_class = MessageTypeTemplateSerializer
  search_fields = '__all__'
  ordering_fields = '__all__'
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context