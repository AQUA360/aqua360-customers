from rest_framework import serializers
from django.db.models import Q

from auth.serializers import UserMinimalSerializer
from ..models import *


class NotificationSerializer(serializers.ModelSerializer):

    handle_all = serializers.BooleanField(required=False, allow_null=True, write_only=True)

    read_by = UserMinimalSerializer(many=True, required=False, allow_null=True)
    archived_by = UserMinimalSerializer(many=True, required=False, allow_null=True)

    class Meta:
        model = Notification
        fields = '__all__'

    @staticmethod
    def _set_membership(notifications, field_name, user, add):
        """Afegeix o treu l'usuari d'un M2M de manera idempotent."""
        for notification in notifications:
            manager = getattr(notification, field_name)
            if add:
                manager.add(user)      # si ja hi és, no fa res
            else:
                manager.remove(user)   # si no hi és, no fa res

    def update(self, instance, validated_data):
        handle_all = validated_data.pop('handle_all', None)
        is_seen = validated_data.pop('is_seen', None)
        is_active = validated_data.pop('is_active', None)   # pop, no get: no es desa globalment

        request = self.context.get('request')
        user = request.user if request else None

        instance = super().update(instance, validated_data)

        if handle_all:
            notifications = Notification.objects.filter(
                is_active=True
            ).filter(Q(user=user) | Q(user__isnull=True))
        else:
            notifications = [instance]

        if is_seen is not None:
            # is_seen=True -> llegida, is_seen=False -> no llegida
            self._set_membership(notifications, 'read_by', user, add=bool(is_seen))

        if is_active is not None:
            # is_active=False -> arxivada, is_active=True -> desarxivada
            self._set_membership(notifications, 'archived_by', user, add=not is_active)

        return instance