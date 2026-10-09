from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from ..filters.operator_filter import OperatorFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from auth.permissions import PermissionManager
from rest_framework.decorators import action
from ..models import Operator
from ..serializers.operator_serializer import (
    OperatorSerializer,
    OperatorCreateSerializer,
    OperatorUpdateSerializer
)

class OperatorViewSet(viewsets.ModelViewSet):
    queryset = Operator.objects.all().order_by('token')
    serializer_class = OperatorSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = OperatorFilter
    search_fields = ['token', 'name', 'surname']
    ordering_fields = ['token', 'name', 'surname']
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return OperatorCreateSerializer
        elif self.request.method in ['PUT', 'PATCH']:
            return OperatorUpdateSerializer
        return OperatorSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def create(self, request, *args, **kwargs):
        print(request.data)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = OperatorSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers, content_type='application/json')

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance:Operator = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = OperatorSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_200_OK, content_type='application/json')
    
    def destroy(self, request, *args, **kwargs):
        """
        When deleting an Operator, set the associated ReadingOperator's is_active to False
        instead of deleting it.
        """
        instance = self.get_object()
        
        # If operator has an associated app_user, deactivate it
        if instance.app_user:
            instance.app_user.is_active = False
            instance.app_user.save()
        
        # Delete the operator
        self.perform_destroy(instance)
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
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
            group_permissions = PermissionManager.get_model_group_permissions(group, 'operator')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'operator', 'order')
        return Response(permissions, status=status.HTTP_200_OK)
        
    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()