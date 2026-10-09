from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from ..models import OrderReport
from ..serializers.order_report_serializer import OrderReportSerializer
from ..filters.order_report_filter import OrderReportFilter
from order.permissions import OrderPermission
class OrderReportViewSet(viewsets.ModelViewSet):
  queryset = OrderReport.objects.all().order_by('-created_at')
  serializer_class = OrderReportSerializer
  permission_classes = [IsAuthenticated, OrderPermission]
  filterset_class = OrderReportFilter
  filter_backends = [DjangoFilterBackend, OrderingFilter]
  search_fields = '__all__'
  ordering_fields = '__all__'
    
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context
  