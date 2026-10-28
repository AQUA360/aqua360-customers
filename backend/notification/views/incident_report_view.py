from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from notification.filters.incident_report_filter import IncidentReportFilter
from notification.models import IncidentReport
from notification.serializers.value_objects_serializer import IncidentReportListSerializer, IncidentReportSerializer
from notification.permissions import IncidentPermission

class IncidentReportViewSet(viewsets.ModelViewSet):
  queryset = IncidentReport.objects.filter(is_active=True).order_by('-created_at')
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
  
  def destroy(self, request, *args, **kwargs):
    # Esborrat lògic amb justificant: motiu obligatori, data i usuari
    reason = (request.data.get('deletion_reason') or '').strip()
    if not reason:
      return Response({'deletion_reason': [_("A reason is required to delete the report.")]}, status=status.HTTP_400_BAD_REQUEST)
    instance = self.get_object()
    instance.is_active = False
    instance.deleted_at = timezone.now()
    instance.deleted_by = request.user
    instance.deletion_reason = reason
    instance.save(update_fields=['is_active', 'deleted_at', 'deleted_by', 'deletion_reason', 'updated_at'])
    return Response(status=status.HTTP_204_NO_CONTENT)
