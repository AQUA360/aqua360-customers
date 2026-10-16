import uuid

from rest_framework import serializers

from auth.permissions import PermissionManager

from .cards import get_card

MAX_CARDS = 50


def clean_layout(layout, user=None):
    """
    Normalitza una disposició: descarta les cards desconegudes (o sense permís si
    es passa `user`), dona id a les que no en tenen i valida mida i configuració.
    """
    permissions = PermissionManager.get_user_permissions(user) if user is not None else None
    cleaned = []
    for item in layout or []:
        if not isinstance(item, dict):
            continue
        card = get_card(item.get('key'))
        if not card or (user is not None and not card.is_allowed(user, permissions)):
            continue
        size = item.get('size')
        cleaned.append({
            'id': str(item.get('id') or uuid.uuid4()),
            'key': card.key,
            'size': size if size in card.sizes else card.default_size,
            'config': card.clean_config(item.get('config')),
        })
    return cleaned


class LayoutSerializer(serializers.Serializer):
    layout = serializers.ListField(child=serializers.DictField(), allow_empty=True, max_length=MAX_CARDS)

    def validate_layout(self, value):
        for item in value:
            if not get_card(item.get('key')):
                raise serializers.ValidationError(f"Unknown card '{item.get('key')}'")
        return clean_layout(value)
