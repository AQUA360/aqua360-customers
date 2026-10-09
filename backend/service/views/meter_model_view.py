from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from service.models import MeterModel, MeterManufacturer
from service.serializers.value_objects_serializer import MeterModelSerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter
from service.permissions import MeterPermission
class MeterModelViewSet(viewsets.ModelViewSet):
    queryset = MeterModel.objects.all().order_by('name')
    serializer_class = MeterModelSerializer
    permission_classes = [IsAuthenticated, MeterPermission]
    filter_backends = [SearchFilter] 
    search_fields = ['name']
    
    @action(detail=False, methods=['get'])
    def by_manufacturer(self, request):
        manufacturer_id = request.query_params.get('manufacturer_id', None)

        if not manufacturer_id:
            return Response({"error": "Manufacturer ID is required"}, status=400)

        try:
            manufacturer = MeterManufacturer.objects.get(id=manufacturer_id)
        except MeterManufacturer.DoesNotExist:
            return Response({"error": "Manufacturer not found"}, status=404)

        models = MeterModel.objects.filter(manufacturer=manufacturer).order_by('name')
        serializer = self.get_serializer(models, many=True)
        return Response(serializer.data)