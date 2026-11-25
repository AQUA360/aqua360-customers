"""Rols d'usuari de Customers: superuser, admin o cap (permisos de grup)."""

from django.conf import settings

CANONICAL_SUPERUSER_USERNAME = 'customers'

ROLE_SUPERUSER = 'superuser'
ROLE_ADMIN = 'admin'
ROLE_NONE = 'none'


def is_customers_account(user):
    """True només per al compte tècnic `customers` (autenticat)."""
    return bool(
        user
        and getattr(user, 'is_authenticated', False)
        and getattr(user, 'username', None) == CANONICAL_SUPERUSER_USERNAME
    )


def can_be_superuser(username):
    """`customers` i els comptes de EXTRA_SUPERUSER_USERNAMES (configuració de la instal·lació).

    La llista fa de segona clau: els is_superuser residuals d'abans de separar
    admin i superuser continuen sent admin si no hi són.
    """
    if not username:
        return False
    extra = getattr(settings, 'EXTRA_SUPERUSER_USERNAMES', ())
    return username == CANONICAL_SUPERUSER_USERNAME or username in extra


def is_canonical_superuser(user):
    """True per a `customers` i els superusuaris addicionals configurats, amb is_superuser."""
    return bool(
        getattr(user, 'is_superuser', False)
        and can_be_superuser(getattr(user, 'username', None))
    )


def get_user_role(user):
    """Només els comptes permesos són superuser; qualsevol altre is_superuser es tracta com admin."""
    if is_canonical_superuser(user):
        return ROLE_SUPERUSER
    if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
        return ROLE_ADMIN
    return ROLE_NONE
