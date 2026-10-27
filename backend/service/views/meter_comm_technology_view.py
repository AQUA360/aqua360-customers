import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from service.models import MeterCommTechnology
from service.permissions import MeterPermission
from service.serializers.value_objects_serializer import MeterCommTechnologySerializer
from service.utils.meter_dictionary_service import get_or_create_dictionary_value


logger = logging.getLogger(__name__)


class MeterCommTechnologyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MeterCommTechnology.objects.all().order_by('name')
    serializer_class = MeterCommTechnologySerializer
    permission_classes = [IsAuthenticated, MeterPermission]
    filter_backends = [SearchFilter]
    search_fields = ['name']

    @action(detail=False, methods=['post'], url_path='get-or-create')
    def get_or_create(self, request):
        try:
            technology, created = get_or_create_dictionary_value(
                MeterCommTechnology,
                request.data.get('name'),
            )
        except ValueError:
            logger.exception('Invalid value provided for meter communication technology creation.')
            return Response(
                {'name': ['Invalid value provided.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            self.get_serializer(technology).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
