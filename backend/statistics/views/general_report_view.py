from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from auth.permissions import PermissionManager
from statistics.models import GeneralReport
from statistics.serializers import GeneralReportSerializer
from statistics.filters import GeneralReportFilter
from statistics.permissions import StatisticsPermission


class GeneralReportViewSet(viewsets.ModelViewSet):
    
    queryset = GeneralReport.objects.all().order_by('-created_at')
    serializer_class = GeneralReportSerializer
    filterset_class = GeneralReportFilter
    permission_classes = [IsAuthenticated, StatisticsPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    ordering_fields = ['type', 'start_date', 'end_date']
    
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
            group_permissions = PermissionManager.get_model_group_permissions(group, 'generalreport')
            return Response(group_permissions, status=status.HTTP_200_OK)
        
        order_permissions = PermissionManager.get_model_permissions(request.user, 'order', 'order')
        payment_permissions = PermissionManager.get_model_permissions(request.user, 'payment', 'billing')
        billing_permissions = PermissionManager.get_model_permissions(request.user, 'billing', 'billing')
        
        permissions = self._get_best_permissions([order_permissions, payment_permissions, billing_permissions])
        return Response(permissions, status=status.HTTP_200_OK)
    
    def _get_best_permissions(self, permissions_list):
        for permissions in permissions_list:
            if permissions and any([
                permissions.get('can_view', False),
                permissions.get('can_add', False),
                permissions.get('can_change', False),
                permissions.get('can_delete', False)
            ]):
                return permissions
        return None
        
    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()
