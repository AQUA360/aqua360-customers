import logging

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.decorators import action
from rest_framework.response import Response

from coredata.filters.config_project_filter import ConfigProjectFilter
from coredata.models import ConfigProject
from coredata.permissions import ConfigProjectPermission, visible_config_value
from coredata.serializers import ConfigProjectSerializer


logger = logging.getLogger(__name__)

BULK_UPDATE_MAX_ITEMS = 200
CONFIG_VALUE_MAX_LENGTH = 20000


def _normalize_config_value(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value)
    return str(value)


class ConfigProjectViewSet(viewsets.ModelViewSet):
    queryset = ConfigProject.objects.all()
    serializer_class = ConfigProjectSerializer
    permission_classes = [IsAuthenticated, ConfigProjectPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = ConfigProjectFilter
    search_fields = ['name','token']
    ordering_fields = ['name', 'token']
    lookup_field = 'token'
    pagination_class = None  # Desactiva la paginació per a aquest ViewSet

    @action(detail=True, methods=['get'])
    def value(self, request, token=None):
        config = self.get_object()
        return Response({'value': visible_config_value(config.token, config.value, request.user)})

    @action(detail=False, methods=['post'], url_path='bulk-update-values')
    def bulk_update_values(self, request):
        items = request.data
        if not isinstance(items, list):
            return Response(
                {'detail': 'Espera una llista de {token, value}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(items) > BULK_UPDATE_MAX_ITEMS:
            return Response(
                {'detail': f'Màxim {BULK_UPDATE_MAX_ITEMS} configuracions per petició.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated = []
        errors = []
        seen_tokens = set()

        with transaction.atomic():
            for item in items:
                if not isinstance(item, dict):
                    errors.append({'item': item, 'detail': 'Format invàlid.'})
                    continue

                token = item.get('token')
                if not token or not isinstance(token, str):
                    errors.append({'item': item, 'detail': 'Cal token.'})
                    continue

                if token in seen_tokens:
                    errors.append({'token': token, 'detail': 'Token repetit a la petició.'})
                    continue
                seen_tokens.add(token)

                if 'value' not in item:
                    errors.append({'token': token, 'detail': 'Cal value.'})
                    continue

                # El valor és text: no s'accepten llistes ni objectes (es desarien com a repr de Python)
                if isinstance(item['value'], (dict, list)):
                    errors.append({'token': token, 'detail': 'El valor ha de ser un text, un número o un booleà.'})
                    continue
                if len(str(item['value'])) > CONFIG_VALUE_MAX_LENGTH:
                    errors.append({'token': token, 'detail': 'Valor massa llarg.'})
                    continue

                try:
                    config = ConfigProject.objects.get(token=token)
                except ConfigProject.DoesNotExist:
                    errors.append({'token': token, 'detail': 'ConfigProject no trobat.'})
                    continue

                config.value = _normalize_config_value(item['value'])
                config.save(update_fields=['value', 'updated_at'])
                # Auditoria: quin registre i qui (ni el valor ni el token: poden ser secrets)
                logger.info('ConfigProject id=%s modificat per %s', config.pk, request.user.username)
                updated.append(ConfigProjectSerializer(config, context={'request': request}).data)

        if errors and not updated:
            return Response({'updated': updated, 'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'updated': updated, 'errors': errors}, status=status.HTTP_200_OK)