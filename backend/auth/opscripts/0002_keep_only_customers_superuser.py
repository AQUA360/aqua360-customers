"""Deixa `customers` com a únic superusuari.

Els altres comptes amb is_superuser es rebaixen a admin (is_staff=True):
tots els permisos de negoci, sense gestió d'usuaris/grups.
Si `customers` no existeix, es continua sense crear-lo.
"""


def run():
    from django.contrib.auth.models import User

    from auth.roles import CANONICAL_SUPERUSER_USERNAME

    customers = User.objects.filter(username=CANONICAL_SUPERUSER_USERNAME).first()
    if customers is not None and (not customers.is_superuser or not customers.is_staff):
        customers.is_superuser = True
        customers.is_staff = True
        customers.save(update_fields=['is_superuser', 'is_staff'])

    # Antics "admins" marcats com a superuser → admin real (is_staff).
    User.objects.exclude(username=CANONICAL_SUPERUSER_USERNAME).filter(
        is_superuser=True,
    ).update(is_superuser=False, is_staff=True)
