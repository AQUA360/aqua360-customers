from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from coredata.filters.city_filter import CityFilter
from coredata.models import City
from coredata.serializers import CitySerializer
from pagination.large_pagination import LargeResultsSetPagination
from coredata.permissions import AddressPermission
class CityViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Street to be viewed or edited.
    """
    queryset = City.objects.all().order_by('name')
    serializer_class = CitySerializer
    permission_classes = [IsAuthenticated, AddressPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = CityFilter
    search_fields = ['name', 'token']
    ordering_fields = ['name', 'province', 'token']

class ProvinceCitiesViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Street to be viewed or edited.
    """
    queryset = City.objects.all().order_by('name')
    serializer_class = CitySerializer
    permission_classes = [IsAuthenticated, AddressPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = CityFilter
    search_fields = ['province']
    pagination_class = LargeResultsSetPagination
    def get_queryset(self):
        province_id = self.kwargs.get('id')
        return City.objects.filter(province=province_id).order_by('name')