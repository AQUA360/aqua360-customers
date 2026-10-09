from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from coredata.filters.province_filter import ProvinceFilter
from coredata.models import Province
from coredata.serializers import ProvinceSerializer
from pagination.large_pagination import LargeResultsSetPagination
from coredata.permissions import AddressPermission

class ProvinceViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Street to be viewed or edited.
    """
    queryset = Province.objects.all().order_by('name')
    serializer_class = ProvinceSerializer
    permission_classes = [IsAuthenticated, AddressPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = ProvinceFilter
    search_fields = ['name', 'country']
    ordering_fields = ['name']
    pagination_class = LargeResultsSetPagination
