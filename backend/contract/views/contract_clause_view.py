from rest_framework import viewsets
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend

from contract.models import ContractClause
from contract.serializers.contract_clause_serializer import ContractClauseSerializer
from contract.filters.contract_clause_filter import ContractClauseFilter
from contract.permissions import ContractPermission

class ContractClauseViewSet(viewsets.ModelViewSet):
    queryset = ContractClause.objects.all().order_by('token')
    serializer_class = ContractClauseSerializer
    permission_classes = [IsAuthenticated, ContractPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = ContractClauseFilter
    search_fields = ['token', ]
    ordering_fields = ['token',]
    