from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.decorators import action

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat

from django.conf import settings

from auth.permissions import PermissionManager
from service.filters.cluster_filter import ClusterFilter
from service.models import ClusterObservation, Cluster, ClusterDocumentationType, ClusterDocumentationFile
from service.serializers.cluster_serializer import ClusterSaveSerializer, ClusterSerializer, ClusterListSerializer
from documentmanager.utils.main_utils import upload_document

class ClusterViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows cluster to be viewed or edited.
    """
    queryset = Cluster.objects.all().filter(is_active=True).order_by('token')
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ClusterFilter
    ordering_fields = ['token','address_complete','nb_nozzles','connection_token']
    
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
            Prefetch('observations', queryset=ClusterObservation.objects.order_by('-created_at'))
        )
        return queryset
    
    def get_serializer_class(self):
        if self.request.method in ['GET']:
            if self.action == 'list':  # Corresponds to GET / (list view)
                return ClusterListSerializer
            elif self.action == 'retrieve':  # Corresponds to GET /id (detail view)
                return ClusterSerializer
        return ClusterSaveSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = ClusterSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = ClusterSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data)
    
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
            group_permissions = PermissionManager.get_model_group_permissions(group, 'cluster')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'cluster', 'service')
        return Response(permissions, status=status.HTTP_200_OK)
        
    @action(detail=True, methods=['put'], url_path='save-file')
    def save_file(self, request, pk=None):
        instance = self.get_object()
        file = request.data.get('file', None)
        cluster_type_id = request.data.get('cluster_type', None)

        if not file:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("File is required")

        try:
            cluster_type = ClusterDocumentationType.objects.get(id=cluster_type_id)
        except ClusterDocumentationType.DoesNotExist:
            cluster_type = None

        service = settings.DOCUMENT_MANAGER_SERVICES.get("connection")
        document = upload_document(
            file,
            'CLUSTER',
            'CLUSTER',
            instance.id,
            instance.token,
            '',
            service,
            file.name.replace(' ', '_').replace('/', '_'),
            instance.created_at
        )

        ClusterDocumentationFile.objects.create(
            cluster=instance,
            file=document,
            type=cluster_type
        )

        serializer = ClusterSerializer(instance, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)

    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()