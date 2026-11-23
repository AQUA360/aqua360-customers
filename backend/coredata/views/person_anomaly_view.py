import uuid

from django.db import transaction
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from coredata.filters.person_anomaly_filter import PersonAnomalyFilter
from coredata.models import PersonAnomaly, PersonAnomalyType, PersonLog
from coredata.permissions import PersonPermission, PersonReadPermission
from coredata.serializers import PersonAnomalySerializer, PersonAnomalyTypeSerializer


def _describe(anomaly):
    end = f" - {anomaly.end_date.isoformat()}" if anomaly.end_date else ''
    observation = f": {anomaly.observation}" if anomaly.observation else ''
    return f"{anomaly.anomaly_type.name} ({anomaly.start_date.isoformat()}{end}){observation}"


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


class CanChangePerson(BasePermission):
    """Resoldre una anomalia és modificar-la: cal change_person (PersonPermission lligaria el POST a add_person)."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.has_perm('coredata.change_person'))


class PersonAnomalyTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PersonAnomalyType.objects.filter(is_active=True)
    serializer_class = PersonAnomalyTypeSerializer
    permission_classes = [IsAuthenticated, PersonReadPermission]
    pagination_class = None


class PersonAnomalyViewSet(viewsets.ModelViewSet):
    queryset = PersonAnomaly.objects.filter(is_active=True).select_related('anomaly_type', 'user')
    serializer_class = PersonAnomalySerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = PersonAnomalyFilter
    permission_classes = [IsAuthenticated, PersonPermission]

    def get_permissions(self):
        if self.action == 'resolve':
            return [IsAuthenticated(), CanChangePerson()]
        return super().get_permissions()

    # L'anomalia i la seva línia d'historial es desen juntes o no es desa res
    def perform_create(self, serializer):
        with transaction.atomic():
            anomaly = serializer.save(user=self.request.user)
            _log(anomaly, self.request.user, None, _describe(anomaly))

    def perform_update(self, serializer):
        with transaction.atomic():
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
        with transaction.atomic():
            anomaly.is_active = False
            anomaly.save(update_fields=['is_active', 'updated_at'])
            _log(anomaly, request.user, _describe(anomaly), None)
        return Response(status=status.HTTP_204_NO_CONTENT)
