from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat

from django_filters.rest_framework import DjangoFilterBackend

from documentmanager.utils.main_utils import upload_document
from notification.filters.incident_documentation_filter import IncidentDocumentationFilter
from notification.models import IncidentDocumentation, IncidentReport
from notification.serializers.value_objects_serializer import IncidentDocumentationSerializer
from notification.permissions import IncidentPermission

class IncidentDocumentationViewSet(viewsets.ModelViewSet):
    queryset = IncidentDocumentation.objects.all().order_by('id')
    permission_classes = [IsAuthenticated, IncidentPermission]
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IncidentDocumentationFilter
    search_fields = ['file']
    ordering_fields = ['file']
    
    def get_serializer_class(self):
        return IncidentDocumentationSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        incident_report = IncidentReport.objects.get(id=request.data.get('id'))
        request.data.pop('id')
        file = request.data.pop('file')
        
        serializer.is_valid(raise_exception=True)
        
        service = settings.DOCUMENT_MANAGER_SERVICES.get("communication")
        document = upload_document(file[0], incident_report.incident.token, 'INCIDENT', incident_report.id, incident_report.token, '', service, file[0].name)
        validated_data = serializer.validated_data
        validated_data['incident_report'] = incident_report
        validated_data['file'] = document 
        
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = IncidentDocumentationSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers, content_type='application/json')

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = IncidentDocumentationSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_200_OK, content_type='application/json')