from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

from pagination.large_pagination import LargeResultsSetPagination
from service.utils.meter_dictionary_service import (
    apply_meter_rename,
    collect_meters_to_rename,
    meters_using,
)


class MeterDictionaryViewSetMixin:
    """
    Comportament comú dels diccionaris de comptadors (fabricant, model, tecnologia):
    - llistes sense tallar a 50 (s'usen com a opcions de desplegables),
    - un canvi de nom es propaga al text dels comptadors que el fan servir,
    - no es pot esborrar un valor que algun comptador fa servir. Per a un fabricant
      això inclou els comptadors dels seus models (que s'esborrarien en cascada),
      ja que aquests comptadors també porten el nom del fabricant.
    """
    pagination_class = LargeResultsSetPagination

    def _request_user(self):
        user = getattr(self.request, 'user', None)
        return user if user is not None and user.is_authenticated else None

    def perform_update(self, serializer):
        with transaction.atomic():
            persisted = type(serializer.instance).objects.select_for_update().get(pk=serializer.instance.pk)
            new_name = serializer.validated_data.get('name', persisted.name)
            assigned_manufacturer = self._newly_assigned_manufacturer(persisted, serializer)
            renaming = new_name != persisted.name
            if not renaming and assigned_manufacturer is None:
                serializer.save()
                return

            # Les dues fotos s'han de prendre abans de desar: un cop el model té
            # fabricant, meters_using ja no troba els comptadors amb fabricant buit.
            field, affected = collect_meters_to_rename(persisted) if renaming else (None, [])
            linked_meters = (
                list(meters_using(persisted).values_list('id', 'manufacturer'))
                if assigned_manufacturer is not None
                else []
            )
            serializer.save()
            if renaming:
                apply_meter_rename(field, affected, new_name, user=self._request_user())
            if assigned_manufacturer is not None:
                apply_meter_rename(
                    'manufacturer',
                    linked_meters,
                    assigned_manufacturer.name,
                    user=self._request_user(),
                )

    def _newly_assigned_manufacturer(self, persisted, serializer):
        """Fabricant que s'està posant a un model que fins ara no en tenia."""
        from service.models import MeterModel

        if not isinstance(persisted, MeterModel) or persisted.manufacturer_id:
            return None
        if 'manufacturer' not in serializer.validated_data:
            return None
        return serializer.validated_data['manufacturer']

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        in_use = meters_using(instance).count()
        if in_use:
            return Response(
                {
                    'detail': f'This value is in use by {in_use} meter(s) and cannot be deleted.',
                    'meters_count': in_use,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)
