from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from service.models import MeterCommTechnology
from service.permissions import MeterPermission
from service.serializers.value_objects_serializer import MeterCommTechnologySerializer
from service.utils.meter_dictionary_service import get_or_create_dictionary_value


class MeterCommTechnologyViewSet(viewsets.ModelViewSet):
    queryset = MeterCommTechnology.objects.all().order_by('name')
    serializer_class = MeterCommTechnologySerializer
    permission_classes = [IsAuthenticated, MeterPermission]
    filter_backends = [SearchFilter]
    search_fields = ['name']

    @action(detail=False, methods=['post'], url_path='get-or-create')
    def get_or_create(self, request):
        try:
            technology = get_or_create_dictionary_value(
                MeterCommTechnology,
                request.data.get('name'),
            )
        except ValueError as error:
            return Response({'name': [str(error)]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(technology).data, status=status.HTTP_200_OK)
