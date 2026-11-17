"""Deixa `customers` com a únic superusuari.

Els altres comptes amb is_superuser es rebaixen a admin (is_staff=True):
tots els permisos de negoci, sense gestió d'usuaris/grups.
Si `customers` no existeix, es crea amb password `customers`.
"""


def run():
    from django.contrib.auth.models import User

    from auth.roles import CANONICAL_SUPERUSER_USERNAME

    try:
        customers = User.objects.get(username=CANONICAL_SUPERUSER_USERNAME)
    except User.DoesNotExist:
        customers = User.objects.create_superuser(
            CANONICAL_SUPERUSER_USERNAME,
            'customers@aventec.cat',
            CANONICAL_SUPERUSER_USERNAME,
        )
    else:
        if not customers.is_superuser or not customers.is_staff:
            customers.is_superuser = True
            customers.is_staff = True
            customers.save(update_fields=['is_superuser', 'is_staff'])

    # Antics "admins" marcats com a superuser → admin real (is_staff).
    User.objects.exclude(username=CANONICAL_SUPERUSER_USERNAME).filter(
        is_superuser=True,
    ).update(is_superuser=False, is_staff=True)
