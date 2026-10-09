from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from rest_framework.decorators import action

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat

from django.conf import settings

from auth.permissions import PermissionManager
from service.filters.connection_filter import ConnectionFilter
from coredata.models import PostalCode
from service.models import ConnectionObservation, Connection, ConnectionStatus, ClusterNozzleStatus, ConnectionInstallationType, ClusterNozzleType, ClusterStatus, Cluster, ClusterNozzle, ConnectionDocumentationType, ConnectionDocumentationFile
from service.serializers.connection_serializer import ConnectionSaveSerializer, ConnectionSerializer, ConnectionListSerializer
from coredata.models import ConfigProject
from documentmanager.utils.main_utils import upload_document

class ConnectionViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows connection to be viewed or edited.
    """
    queryset = Connection.objects.filter(is_active=True).all()
    # serializer_class = ConnectionSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ConnectionFilter
    ordering_fields = ['token', 'installation_at','dma_name','exploitation_name','use_type_name','diameter_name','status_name']

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.annotate(
            status_token=F('status__name'),
            status_name=F('status__name'),
            exploitation_name=F('exploitation__name'),
            exploitation_token=F('exploitation__token'), 
            dma_name=F('dma__name'),
            diameter_name=F('diameter__name'),
            use_type_name=F('use_type__name')
        ).prefetch_related(
            Prefetch('observations', queryset=ConnectionObservation.objects.order_by('-created_at'))
        )
        return queryset
    
    def get_serializer_class(self):
        if self.request.method in ['GET']:
            if self.action == 'list':  # Corresponds to GET / (list view)
                return ConnectionListSerializer
            elif self.action == 'retrieve':  # Corresponds to GET /id (detail view)
                return ConnectionSerializer
        return ConnectionSaveSerializer
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['post'], url_path='activate')
    def activate(self, request, pk=None):
        """
        Activate a connection by changing its status.
        Expects 'status_id' in request data to specify the new status.
        """
        connection = self.get_object()
        
        # Get the new status ID from request data
        conn_status = ConnectionStatus.objects.get(token=ConfigProject.objects.get(token='connection_status_active_token').value)

        connection.status = conn_status
        connection.save()
        
        return Response({
            'message': f'Connection status updated',
        }, status=status.HTTP_200_OK)
        
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
            group_permissions = PermissionManager.get_model_group_permissions(group, 'connection')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'connection', 'service')
        return Response(permissions, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['put'], url_path='convert-to-cluster')
    def convert_to_cluster(self, request, pk=None):
        connection = self.get_object()
        
        connection_supply_type = ConnectionInstallationType.objects.get(token='cluster')
        connection.installation_type = connection_supply_type
        connection.save()
        
        cluster_status = ClusterStatus.objects.get(is_default=True)
        
        sp = connection.supply_points.first()
        
        if sp:
            postalCode, _ = PostalCode.objects.get_or_create(code=sp.address.postal_code)
            
            cluster = Cluster.objects.create(
                token=connection.token,
                connection=connection,
                status=cluster_status,
                nb_nozzles = 1,
                address_street = sp.address.street if sp.address else None,
                address_street_number = sp.address.street_number if sp.address else None,
                address_postal_code = postalCode if postalCode else None,
                address_city = sp.address.city if sp.address else None,
                property = sp.property if sp.property else None
            )
            
            cluster_nozzle = ClusterNozzle.objects.create(
                token=connection.token + '/1',
                cluster=cluster,
                status=ClusterNozzleStatus.objects.get(is_default=True),
                type=ClusterNozzleType.objects.get(is_default=True),
                position=1,
                col=1,
                row=1
            )
            
            
            sp.cluster_nozzle = cluster_nozzle
            sp.save()
        
        return Response({'message': 'Connection converted to cluster'}, status=status.HTTP_200_OK)
        
    @action(detail=True, methods=['put'], url_path='save-file')
    def save_file(self, request, pk=None):
        instance = self.get_object()
        file = request.data.get('file', None)
        connection_type_id = request.data.get('connection_type', None)

        if not file:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("File is required")

        try:
            connection_type = ConnectionDocumentationType.objects.get(id=connection_type_id)
        except ConnectionDocumentationType.DoesNotExist:
            connection_type = None

        service = settings.DOCUMENT_MANAGER_SERVICES.get("connection")
        document = upload_document(
            file,
            'CONNECTION',
            'CONNECTION',
            instance.id,
            instance.token,
            '',
            service,
            file.name.replace(' ', '_').replace('/', '_'),
            instance.created_at
        )

        ConnectionDocumentationFile.objects.create(
            connection=instance,
            file=document,
            type=connection_type
        )

        serializer = ConnectionSerializer(instance, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)

    def get_permissions(self):
        if self.action in ['permissions', 'activate']:
            return [IsAuthenticated()]
        return super().get_permissions()
