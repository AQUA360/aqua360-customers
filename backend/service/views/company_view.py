from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.decorators import action

from auth.permissions import PermissionManager
from service.filters.company_filter import CompanyFilter
from service.models import Company 
from service.serializers.company_serializer import CompanySerializer
from rest_framework.response import Response
from rest_framework import status

class CompanyViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Company to be viewed or edited.
    """
    queryset = Company.objects.all().filter(is_active=True).order_by('name')
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filterset_class = CompanyFilter
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
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
            group_permissions = PermissionManager.get_model_group_permissions(group, 'company')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'company', 'service')
        return Response(permissions, status=status.HTTP_200_OK)
        
    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()