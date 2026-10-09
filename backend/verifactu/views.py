from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from django.contrib.auth.models import Group
from auth.permissions import PermissionManager

from billing.models import Invoice
from verifactu.models import VerifactuNotification, VerifactuNotificationLog, VerifactuBatch
from verifactu.serializers.verifactu_serializer import VerifactuBatchSerializer, VerifactuNotificationLogSerializer, VerifactuNotificationSerializer
from verifactu.filters.verifactu_notification_filter import VerifactuNotificationFilter
from verifactu.utils.save_verifactu_info import create_verifactu_invoice


class VerifactuNotificationViewSet(viewsets.ModelViewSet):
    queryset = VerifactuNotification.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated]
    serializer_class = VerifactuNotificationSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = VerifactuNotificationFilter
    ordering_fields = ['created_at', 'token', 'response_status', 'invoice_cancelled']
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    @action(detail=False, methods=['put'], url_path='(?P<invoice_id>[^/.]+)/notify-verifactu')
    def notify_verifactu(self, request, invoice_id=None):
        if not invoice_id:
            return Response(
                {"detail": "Missing invoice_id in URL."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            invoice = Invoice.objects.get(id=invoice_id)
        except Invoice.DoesNotExist:
            return Response(
                {"detail": f"Invoice with id {invoice_id} not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if invoice.verifactu_notification is not None:
            return Response(
                {"detail": "Invoice already has a verifactu_notification."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            verifactu_notification = create_verifactu_invoice(invoice, single_batch=True)
            return Response({
                "message": f"Successfully created and notified Verifactu for invoice {invoice_id}",
                "verifactu_notification_id": verifactu_notification.id,
                "batch_id": verifactu_notification.batch.id if verifactu_notification.batch else None,
                "batch_status": verifactu_notification.batch.response_status if verifactu_notification.batch else None
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"detail": f"Error creating/notifying Verifactu: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'], url_path='logs')
    def logs(self, request, pk=None):
        try:
            verifactu_notification = self.get_object()
            logs = VerifactuNotificationLog.objects.filter(verifactu_notification=verifactu_notification).order_by('-created_at')
            serializer = VerifactuNotificationLogSerializer(logs, many=True, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except VerifactuNotification.DoesNotExist:
            return Response(
                {"error": "VerifactuNotification not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
            
    # Permissions
    @action(detail=False, methods=['get'], url_path='permissions')
    def permissions(self, request):
        pk = request.query_params.get('id')
        if pk:
            user_permissions = PermissionManager.get_model_permissions(request.user, 'auth', 'group')
            if not user_permissions['can_view'] or not user_permissions['can_change'] or not request.user.is_superuser:
                return Response( None, status=status.HTTP_403_FORBIDDEN )
            group = Group.objects.filter(id=pk).first()
            if not group:
                return Response( None, status=status.HTTP_404_NOT_FOUND )
            group_permissions = PermissionManager.get_model_group_permissions(group, 'invoice')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'invoice', 'billing')
        return Response(permissions, status=status.HTTP_200_OK)
        
    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()

class VerifactuBatchViewSet(viewsets.ModelViewSet):
    queryset = VerifactuBatch.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated]
    serializer_class = VerifactuBatchSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
            
    # Permissions
    @action(detail=False, methods=['get'], url_path='permissions')
    def permissions(self, request):
        pk = request.query_params.get('id')
        if pk:
            user_permissions = PermissionManager.get_model_permissions(request.user, 'auth', 'group')
            if not user_permissions['can_view'] or not user_permissions['can_change'] or not request.user.is_superuser:
                return Response( None, status=status.HTTP_403_FORBIDDEN )
            group = Group.objects.filter(id=pk).first()
            if not group:
                return Response( None, status=status.HTTP_404_NOT_FOUND )
            group_permissions = PermissionManager.get_model_group_permissions(group, 'invoice')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'invoice', 'billing')
        return Response(permissions, status=status.HTTP_200_OK)
        
    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()
    