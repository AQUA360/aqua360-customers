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
        """Reject unknown card keys and normalize the submitted layout."""
        for item in value:
            if not get_card(item.get('key')):
                raise serializers.ValidationError(f"Unknown card '{item.get('key')}'")
        return clean_layout(value)


MAX_SIDEBAR_KEYS = 100
MAX_SIDEBAR_KEY_LENGTH = 64
MAX_SIDEBAR_RECENT = 5


def _clean_keys(value):
    """Keep the distinct, short string keys of a list, in their order."""
    if not isinstance(value, list):
        return []
    keys = []
    for key in value:
        if isinstance(key, str) and 0 < len(key) <= MAX_SIDEBAR_KEY_LENGTH and key not in keys:
            keys.append(key)
        if len(keys) >= MAX_SIDEBAR_KEYS:
            break
    return keys


def _clean_hidden_and_order(value):
    """Normalize a {"hidden": [...], "order": [...]} block."""
    value = value if isinstance(value, dict) else {}
    return {'hidden': _clean_keys(value.get('hidden')), 'order': _clean_keys(value.get('order'))}


def clean_sidebar_layout(layout):
    """
    Normalitza la personalització del menú lateral: només llistes de claus
    curtes, sense repetits, i amb un límit de seccions i enllaços.
    """
    layout = layout if isinstance(layout, dict) else {}
    items = layout.get('items') if isinstance(layout.get('items'), dict) else {}
    cleaned_items = {}
    for section_key, section_items in items.items():
        if len(cleaned_items) >= MAX_SIDEBAR_KEYS:
            break
        if isinstance(section_key, str) and 0 < len(section_key) <= MAX_SIDEBAR_KEY_LENGTH:
            cleaned_items[section_key] = _clean_hidden_and_order(section_items)
    return {
        'sections': _clean_hidden_and_order(layout.get('sections')),
        'folded': _clean_keys(layout.get('folded')),
        'items': cleaned_items,
        # Enllaços preferits, en l'ordre de l'usuari, com a "<secció>/<enllaç>".
        'favorites': _clean_keys(layout.get('favorites')),
        # Darrers enllaços visitats, del més recent al més antic.
        'recent': _clean_keys(layout.get('recent'))[:MAX_SIDEBAR_RECENT],
    }


class SidebarLayoutSerializer(serializers.Serializer):
    layout = serializers.DictField()

    def validate_layout(self, value):
        """Normalize the submitted sidebar layout."""
        return clean_sidebar_layout(value)
