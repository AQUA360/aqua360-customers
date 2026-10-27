from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from service.models import MeterManufacturer
from service.serializers.value_objects_serializer import MeterManufacturerSerializer
from rest_framework.filters import SearchFilter
from service.permissions import MeterPermission
from service.utils.meter_dictionary_service import get_or_create_dictionary_value

class MeterManufacturerViewSet(viewsets.ModelViewSet):
    queryset = MeterManufacturer.objects.all().order_by('name')
    serializer_class = MeterManufacturerSerializer
    permission_classes = [IsAuthenticated, MeterPermission]
    filter_backends = [SearchFilter] 
    search_fields = ['name']

    @action(detail=False, methods=['post'], url_path='get-or-create')
    def get_or_create(self, request):
        try:
            manufacturer = get_or_create_dictionary_value(
                MeterManufacturer,
                request.data.get('name'),
            )
        except ValueError as error:
            return Response({'name': [str(error)]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(manufacturer).data, status=status.HTTP_200_OK)