from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from coredata.filters.street_number_filter import StreetNumberFilter

from coredata.models import StreetNumber
from coredata.serializers import StreetNumberSerializer
from coredata.permissions import AddressPermission
class StreetNumberViewSet(viewsets.ModelViewSet):
    queryset = StreetNumber.objects.all().order_by('number_type', 'number')
    serializer_class = StreetNumberSerializer
    permission_classes = [IsAuthenticated, AddressPermission]
    filterset_class = StreetNumberFilter
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields = '__all__'
    ordering_fields = '__all__'
