from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.decorators import action
from rest_framework.response import Response

from coredata.filters.config_project_filter import ConfigProjectFilter
from coredata.models import ConfigProject
from coredata.serializers import ConfigProjectSerializer


def _normalize_config_value(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value)
    return str(value)


class ConfigProjectViewSet(viewsets.ModelViewSet):
    queryset = ConfigProject.objects.all()
    serializer_class = ConfigProjectSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = ConfigProjectFilter
    search_fields = ['name','token']
    ordering_fields = ['name', 'token']
    lookup_field = 'token'
    pagination_class = None  # Desactiva la paginació per a aquest ViewSet

    @action(detail=True, methods=['get'])
    def value(self, request, token=None):
        config = self.get_object()
        return Response({'value': config.value})

    @action(detail=False, methods=['post'], url_path='bulk-update-values')
    def bulk_update_values(self, request):
        items = request.data
        if not isinstance(items, list):
            return Response(
                {'detail': 'Espera una llista de {token, value}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated = []
        errors = []

        with transaction.atomic():
            for item in items:
                if not isinstance(item, dict):
                    errors.append({'item': item, 'detail': 'Format invàlid.'})
                    continue

                token = item.get('token')
                if not token:
                    errors.append({'item': item, 'detail': 'Cal token.'})
                    continue

                if 'value' not in item:
                    errors.append({'token': token, 'detail': 'Cal value.'})
                    continue

                try:
                    config = ConfigProject.objects.get(token=token)
                except ConfigProject.DoesNotExist:
                    errors.append({'token': token, 'detail': 'ConfigProject no trobat.'})
                    continue

                config.value = _normalize_config_value(item['value'])
                config.save(update_fields=['value', 'updated_at'])
                updated.append(ConfigProjectSerializer(config).data)

        if errors and not updated:
            return Response({'updated': updated, 'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'updated': updated, 'errors': errors}, status=status.HTTP_200_OK)