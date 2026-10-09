from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from statistics.models import BillingReport
from statistics.serializers import BillingReportSerializer
from statistics.filters import BillingReportFilter
from statistics.permissions import StatisticsPermission


class BillingReportViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Zone to be viewed or edited.
    """
    queryset = BillingReport.objects.all().order_by('created_at')
    serializer_class = BillingReportSerializer
    filterset_class = BillingReportFilter
    permission_classes = [IsAuthenticated, StatisticsPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    ordering_fields = ['type', 'start_date', 'end_date']
