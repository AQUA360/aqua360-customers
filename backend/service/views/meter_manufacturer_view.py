from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from service.models import MeterManufacturer
from service.serializers.value_objects_serializer import MeterManufacturerSerializer
from rest_framework.filters import SearchFilter
from service.permissions import MeterPermission
class MeterManufacturerViewSet(viewsets.ModelViewSet):
    queryset = MeterManufacturer.objects.all().order_by('name')
    serializer_class = MeterManufacturerSerializer
    permission_classes = [IsAuthenticated, MeterPermission]
    filter_backends = [SearchFilter] 
    search_fields = ['name']