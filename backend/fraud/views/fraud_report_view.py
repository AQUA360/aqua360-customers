from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from fraud.filters.fraud_report_filter import FraudReportFilter
from fraud.models import FraudReport
from fraud.serializers.fraud_report_serializer import *
from fraud.permissions import FraudPermission

class FraudReportViewSet(viewsets.ModelViewSet):
  queryset = FraudReport.objects.all().order_by('-created_at')
  serializer_class = FraudReportSerializer
  permission_classes = [IsAuthenticated, FraudPermission]
  filterset_class = FraudReportFilter
  filter_backends = [DjangoFilterBackend, OrderingFilter]
  search_fields = '__all__'
  ordering_fields = '__all__'
    
  def get_serializer_class(self):
    if self.request.method in ['GET']:
      if self.action == 'list':  
            return FraudReportListSerializer
      elif self.action == 'retrieve':
            return FraudReportSerializer
    return FraudReportSaveSerializer
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context
  