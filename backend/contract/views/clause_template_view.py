from rest_framework import viewsets
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend

from contract.models import ClauseTemplate
from contract.serializers.clause_template_serializer import ClauseTemplateSerializer
from contract.permissions import ContractRequestPermission

class ClauseTemplateViewSet(viewsets.ModelViewSet):
    queryset = ClauseTemplate.objects.all().order_by('token')
    serializer_class = ClauseTemplateSerializer
    permission_classes = [IsAuthenticated, ContractRequestPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['token', 'title', 'clause']
    ordering_fields = ['token', 'title']
    