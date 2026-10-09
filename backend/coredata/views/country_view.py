from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from coredata.models import Country
from coredata.serializers import CountrySerializer
from pagination.large_pagination import LargeResultsSetPagination
from coredata.permissions import AddressPermission
class CountryViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Street to be viewed or edited.
    """
    queryset = Country.objects.all().order_by('name')
    serializer_class = CountrySerializer
    permission_classes = [IsAuthenticated, AddressPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields = ['name']
    ordering_fields = ['name']
    pagination_class = LargeResultsSetPagination
