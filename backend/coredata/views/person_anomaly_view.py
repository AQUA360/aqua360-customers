import uuid

from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from coredata.filters.person_anomaly_filter import PersonAnomalyFilter
from coredata.models import PersonAnomaly, PersonAnomalyType, PersonLog
from coredata.permissions import PersonPermission
from coredata.serializers import PersonAnomalySerializer, PersonAnomalyTypeSerializer


def _describe(anomaly):
    end = f" - {anomaly.end_date.isoformat()}" if anomaly.end_date else ''
    return f"{anomaly.anomaly_type.name} ({anomaly.start_date.isoformat()}{end})"


def _log(anomaly, user, old_value, new_value):
    """Deixa l'alta, la modificació o la baixa de l'anomalia a l'historial de canvis de la persona."""
    PersonLog.objects.create(
        person=anomaly.person,
        field_name='anomaly',
        old_value=old_value,
        new_value=new_value,
        operation_token=str(uuid.uuid4()),
        user=user,
    )


class PersonAnomalyTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PersonAnomalyType.objects.filter(is_active=True)
    serializer_class = PersonAnomalyTypeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None


class PersonAnomalyViewSet(viewsets.ModelViewSet):
    queryset = PersonAnomaly.objects.filter(is_active=True).select_related('anomaly_type', 'user')
    serializer_class = PersonAnomalySerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = PersonAnomalyFilter
    permission_classes = [IsAuthenticated, PersonPermission]

    def perform_create(self, serializer):
        anomaly = serializer.save(user=self.request.user)
        _log(anomaly, self.request.user, None, _describe(anomaly))

    def perform_update(self, serializer):
        old_value = _describe(serializer.instance)
        anomaly = serializer.save()
        new_value = _describe(anomaly)
        if new_value != old_value:
            _log(anomaly, self.request.user, old_value, new_value)

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Dona l'anomalia per resolta amb la data indicada (per defecte, avui)."""
        anomaly = self.get_object()
        serializer = self.get_serializer(
            anomaly, data={'end_date': request.data.get('end_date') or timezone.now().date()}, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        anomaly = self.get_object()
        anomaly.is_active = False
        anomaly.save(update_fields=['is_active', 'updated_at'])
        _log(anomaly, request.user, _describe(anomaly), None)
        return Response(status=status.HTTP_204_NO_CONTENT)
