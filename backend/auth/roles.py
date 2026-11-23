"""Rols d'usuari de Customers: superuser, admin o cap (permisos de grup)."""

CANONICAL_SUPERUSER_USERNAME = 'customers'

ROLE_SUPERUSER = 'superuser'
ROLE_ADMIN = 'admin'
ROLE_NONE = 'none'


def is_canonical_superuser(user):
    """True només per al compte `customers` amb is_superuser."""
    return bool(
        getattr(user, 'is_superuser', False)
        and getattr(user, 'username', None) == CANONICAL_SUPERUSER_USERNAME
    )


def get_user_role(user):
    """Només `customers` és superuser; qualsevol altre is_superuser es tracta com admin."""
    if is_canonical_superuser(user):
        return ROLE_SUPERUSER
    if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
        return ROLE_ADMIN
    return ROLE_NONE
