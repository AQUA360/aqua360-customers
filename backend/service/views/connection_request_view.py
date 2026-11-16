# connection_request_view.py
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.decorators import action

from auth.permissions import PermissionManager
from django_filters.rest_framework import DjangoFilterBackend

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import ValidationError

from documentmanager.utils.main_utils import upload_document
from service.models import ConnectionRequest, ConnectionRequestObservation, ConnectionDocumentationType, ConnectionRequestDocumentationFile
from service.serializers.connection_request_serializer import ConnectionRequestSerializer, ConnectionRequestSaveSerializer, ConnectionRequestListSerializer
from service.filters.connection_request_filter import ConnectionRequestFilter

# Només es pot eliminar una sol·licitud que encara no s'ha tramitat.
DELETABLE_STATUS_TOKENS = ('draft', 'pending')

class ConnectionRequestViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows ConnectionRequest to be viewed or edited.
    """
    queryset = ConnectionRequest.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = ConnectionRequestFilter
    search_fields = ['token', 'address_street__name', 'person__name', 'person__surname']
    ordering_fields = ['address_complete','status_name','connection_token']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.annotate(
            address_complete=Concat(
                F('address_street__name'), Value(' '), F('address_street_number'), Value(' '), F('address_city'), output_field=CharField()
            ),
            connection_token=F('connection__token'),
            connection_exploitation_name=F('connection__exploitation__name'),
            status_name=F('status__name')
        ).prefetch_related(
            Prefetch('observations', queryset=ConnectionRequestObservation.objects.order_by('-created_at'))
        )
        return queryset
    
    def get_serializer_class(self):
        if self.request.method in ['GET']:
            if self.action == 'list':  # Corresponds to GET / (list view)
                return ConnectionRequestListSerializer
            elif self.action == 'retrieve':  # Corresponds to GET /id (detail view)
                return ConnectionRequestSerializer
        return ConnectionRequestSaveSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = ConnectionRequestSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = ConnectionRequestSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data)
    
    def destroy(self, request, *args, **kwargs):
        from billing.models import Invoice
        from documentmanager.models import Document
        from logger.models import LogConnectionRequestStatus
        from order.models import Order

        with transaction.atomic():
            instance = ConnectionRequest.objects.select_for_update().get(pk=self.get_object().pk)
            status_token = instance.status.token if instance.status else None
            if status_token not in DELETABLE_STATUS_TOKENS:
                return Response({'error': 'not_deletable_status'}, status=status.HTTP_400_BAD_REQUEST)
            # Que no quedin escomeses, factures ni ordres sense saber d'on venen.
            if ((instance.connection and instance.connection.is_active)
                    or Invoice.objects.filter(connection_request=instance, is_active=True).exists()
                    or Order.objects.filter(connection_request=instance, is_active=True).exists()):
                return Response({'error': 'has_related_records'}, status=status.HTTP_400_BAD_REQUEST)
            LogConnectionRequestStatus.objects.filter(object=instance).delete()
            # Com l'esborrat de documents del gestor documental: es desactiven, no s'esborra el fitxer.
            Document.objects.filter(
                id__in=instance.documentation_files.filter(file__isnull=False).values('file_id')
            ).update(is_active=False)
            instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['put'], url_path='save-file')
    def save_file(self, request, pk=None):
        instance = self.get_object()
        file = request.data.get('file', None)
        if not file:
            raise ValidationError("File is required")

        doc_type = ConnectionDocumentationType.objects.filter(id=request.data.get('doc_type') or None).first()

        document = upload_document(
            file,
            'CONNECTION_REQUEST',
            'CONNECTION_REQUEST',
            instance.id,
            instance.token,
            '',
            settings.DOCUMENT_MANAGER_SERVICES.get("connection"),
            file.name.replace(' ', '_').replace('/', '_'),
            instance.created_at
        )
        ConnectionRequestDocumentationFile.objects.create(
            connection_request=instance,
            file=document,
            type=doc_type
        )

        serializer = ConnectionRequestSerializer(instance, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)

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
            group_permissions = PermissionManager.get_model_group_permissions(group, 'connectionrequest')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'connectionrequest', 'service')
        return Response(permissions, status=status.HTTP_200_OK)
        
    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()