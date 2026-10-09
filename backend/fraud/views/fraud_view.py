from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.decorators import action

from auth.permissions import PermissionManager
from fraud.filters.fraud_filter import FraudFilter
from fraud.models import Fraud
from fraud.serializers.fraud_serializer import FraudSerializer, FraudListSerializer, FraudSaveSerializer


class FraudViewSet(viewsets.ModelViewSet):
  queryset = Fraud.objects.all().order_by('status','-created_at')
  serializer_class = FraudSerializer
  permission_classes = [IsAuthenticated, DjangoModelPermissions]
  filterset_class = FraudFilter
  filter_backends = [DjangoFilterBackend, OrderingFilter]
  search_fields = '__all__'
  ordering_fields = '__all__'
    
  def get_serializer_class(self):
    if self.request.method in ['GET']:
        if self.action == 'list':  
            return FraudListSerializer
        elif self.action == 'retrieve':
            return FraudSerializer
    return FraudSaveSerializer
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context
  
  @action(detail=False, methods=['get'], url_path='permissions')
  def permissions(self, request):
      pk = request.query_params.get('id')
      if pk:
          from django.contrib.auth.models import Group
          user_permissions = PermissionManager.get_model_permissions(request.user, 'auth', 'group')
          if not user_permissions['can_view'] or not user_permissions['can_change'] or not request.user.is_superuser:
              return Response( None, status=status.HTTP_403_FORBIDDEN )
          group = Group.objects.filter(id=pk).first()
          if not group:
              return Response( None, status=status.HTTP_404_NOT_FOUND )
          group_permissions = PermissionManager.get_model_group_permissions(group, 'fraud')
          return Response(group_permissions, status=status.HTTP_200_OK)
      permissions = PermissionManager.get_model_permissions(request.user, 'fraud', 'fraud')
      return Response(permissions, status=status.HTTP_200_OK)
      
  def get_permissions(self):
      if self.action == 'permissions':
          return [IsAuthenticated()]
      return super().get_permissions()