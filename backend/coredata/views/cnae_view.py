from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from coredata.filters.cnae_filter import CnaeFilter
from coredata.models import (CNAE)
from coredata.serializers import (CnaeSerializer)
from coredata.permissions import PersonPermission
class CnaeViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Street to be viewed or edited.
    """
    queryset = CNAE.objects.all().order_by('token')
    serializer_class = CnaeSerializer
    permission_classes = [IsAuthenticated, PersonPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = CnaeFilter
    search_fields = ['description', 'token']
    ordering_fields = ['description', 'province', 'token']