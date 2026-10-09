from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat

from communication.models import Message
from communication.serializers.message_serializer import MessageSerializer, MessageListSerializer, MessageSaveSerializer
from communication.permissions import CommunicationPermission
class MessageViewSet(viewsets.ModelViewSet):
  queryset = Message.objects.all().filter().order_by('-created_at')
  permission_classes = [IsAuthenticated, CommunicationPermission]
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  search_fields = ['token','name']
  ordering_fields = ['token','name']
  
  def get_serializer_class(self):
    
    if self.request.method in ['GET']:
        if self.action == 'list':  
            return MessageListSerializer
        elif self.action == 'retrieve':
            return MessageSerializer
    return MessageSaveSerializer
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context