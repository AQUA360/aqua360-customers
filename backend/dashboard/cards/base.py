"""
Registre de cards del dashboard.

Cada card és una subclasse de DashboardCard registrada amb `@register`. El
frontend demana el catàleg (les cards que l'usuari pot fer servir segons els
seus permisos) i després les dades de cada card per separat, de manera que una
card lenta no bloqueja la resta de la pàgina.

Les cards amb `has_data = False` només existeixen al frontend (p. ex. els
accessos ràpids o el calendari, que ja tenen els seus propis endpoints); es
registren igualment perquè el catàleg i els permisos siguin d'un sol lloc.
"""
import datetime

from django.utils import timezone

from auth.permissions import PermissionManager

SIZES = ['sm', 'md', 'lg']

_REGISTRY = {}


def register(card_class):
    """Register a card instance, rejecting duplicate keys; return its class."""
    card = card_class()
    if card.key in _REGISTRY:
        raise ValueError(f"Dashboard card '{card.key}' already registered")
    _REGISTRY[card.key] = card
    return card_class


def get_card(key):
    """Return the registered card for a string key, or None if unknown."""
    return _REGISTRY.get(key) if isinstance(key, str) else None


def all_cards():
    """Return all registered dashboard card instances."""
    return list(_REGISTRY.values())


def available_cards(user):
    """Return cards allowed by the user permissions."""
    permissions = PermissionManager.get_user_permissions(user)
    return [card for card in _REGISTRY.values() if card.is_allowed(user, permissions)]


class DashboardCard:
    key = None
    # Clau de MainPermission (view_order, view_billing...). None: tothom.
    permission = None
    default_size = 'md'
    sizes = SIZES
    has_data = True
    # Opcions configurables: [{"name", "type": "select|boolean", "options": [...], "default"}]
    config_schema = []

    def is_allowed(self, user, permissions=None):
        """Check the card permission, optionally using preloaded permissions."""
        if not self.permission:
            return True
        if permissions is None:
            return PermissionManager.has_permission(user, self.permission)
        return bool(permissions.get(self.permission, False))

    def clean_config(self, config):
        """Valors per defecte + descarta les opcions desconegudes o no vàlides."""
        config = config if isinstance(config, dict) else {}
        cleaned = {}
        for option in self.config_schema:
            value = config.get(option['name'], option.get('default'))
            if option['type'] == 'select' and value not in [o['value'] for o in option['options']]:
                value = option.get('default')
            elif option['type'] == 'boolean':
                value = value in (True, 'true', '1', 1)
            cleaned[option['name']] = value
        return cleaned

    def get_data(self, user, config):
        """Return card data for the user and cleaned config; subclasses must implement."""
        raise NotImplementedError

    def describe(self):
        """Return catalog metadata describing sizes and configuration options."""
        return {
            'key': self.key,
            'default_size': self.default_size,
            'sizes': self.sizes,
            'has_data': self.has_data,
            'config_schema': self.config_schema,
        }


# Període comú a les cards de facturació.
PERIOD_OPTION = {
    'name': 'period',
    'type': 'select',
    'default': 'month',
    'options': [
        {'value': 'today'},
        {'value': 'week'},
        {'value': 'month'},
        {'value': 'quarter'},
        {'value': 'year'},
    ],
}


def period_range(period, today=None):
    """(data_inici, data_fi) del període que conté avui."""
    today = today or timezone.localdate()
    if period == 'today':
        return today, today
    if period == 'week':
        start = today - datetime.timedelta(days=today.weekday())
        return start, start + datetime.timedelta(days=6)
    if period == 'quarter':
        first_month = 3 * ((today.month - 1) // 3) + 1
        start = today.replace(month=first_month, day=1)
        end_month = first_month + 2
        end = (start.replace(month=end_month, day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)
        return start, end
    if period == 'year':
        return today.replace(month=1, day=1), today.replace(month=12, day=31)
    start = today.replace(day=1)
    end = (start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)
    return start, end


def config_value(token, default=None):
    """Return a project configuration value, falling back when missing or empty."""
    from coredata.models import ConfigProject

    config = ConfigProject.objects.filter(token=token).first()
    return config.value if config and config.value not in (None, '') else default
