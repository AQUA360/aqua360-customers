from django.utils import timezone
from rest_framework.decorators import action

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets, status
from rest_framework.response import Response
from auth.permissions import PermissionManager
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from django.contrib.auth.models import Group

from pricing.filters.accounting_concept_filter import AccountingConceptFilter
from pricing.models import AccountingConcept
from pricing.serializers.accounting_pricing_serializer import AccountingConceptSerializer
from billing.permissions import BillingPermission

class AccountingConceptViewSet(viewsets.ModelViewSet):
    queryset = AccountingConcept.objects.all().order_by('token')
    serializer_class = AccountingConceptSerializer
    permission_classes = [IsAuthenticated, BillingPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = AccountingConceptFilter
    
    def get_serializer_class(self):
        return AccountingConceptSerializer

    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()