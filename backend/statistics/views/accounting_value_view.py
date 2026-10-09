from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from statistics.models import AccountingValue
from statistics.serializers import AccountingValueSerializer
from statistics.permissions import StatisticsPermission


class AccountingValueViewSet(viewsets.ModelViewSet):
    queryset = AccountingValue.objects.all().order_by('created_at')
    serializer_class = AccountingValueSerializer
    permission_classes = [IsAuthenticated, StatisticsPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    ordering_fields = ['code', 'description']
