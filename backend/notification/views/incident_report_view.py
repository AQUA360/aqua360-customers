from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from notification.filters.incident_report_filter import IncidentReportFilter
from notification.models import IncidentReport
from notification.serializers.value_objects_serializer import IncidentReportListSerializer, IncidentReportSerializer
from notification.permissions import IncidentPermission

class IncidentReportViewSet(viewsets.ModelViewSet):
  queryset = IncidentReport.objects.all().order_by('-created_at')
  serializer_class = IncidentReportSerializer
  permission_classes = [IsAuthenticated, IncidentPermission]
  filterset_class = IncidentReportFilter
  filter_backends = [DjangoFilterBackend, OrderingFilter]
  search_fields = '__all__'
  ordering_fields = '__all__'
  
  def get_serializer_class(self):
    if self.request.method in ['GET']:
      if self.action == 'list':  
            return IncidentReportListSerializer
      elif self.action == 'retrieve':
            return IncidentReportSerializer
    return IncidentReportSerializer
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context
  