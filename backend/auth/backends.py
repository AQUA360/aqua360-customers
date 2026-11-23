"""Auth backends per al rol admin (is_staff sense ser el superusuari canònic)."""

from django.contrib.auth.backends import BaseBackend

# Escriptura de gestió d'usuaris/grups/permisos: només el superusuari canònic
# (User.has_perm ja retorna True per is_superuser abans d'arribar als backends).
AUTH_USER_MGMT_WRITE_PERMS = frozenset({
    f'auth.{action}_{model}'
    for model in ('user', 'group', 'permission')
    for action in ('add', 'change', 'delete')
})


class AdminRoleBackend(BaseBackend):
    """Rol admin (`is_staff`, no superuser): tots els permisos de negoci.

    Substitueix l'antic comportament on els "admins" eren `is_superuser` i
    Django els donava tots els `has_perm`. Ara són `is_staff` i aquest backend
    els concedeix els mateixos permisos excepte add/change/delete d'auth.
    """

    def authenticate(self, request, **kwargs):
        return None

    def has_perm(self, user_obj, perm, obj=None):
        if not getattr(user_obj, 'is_active', False):
            return False
        if not getattr(user_obj, 'is_authenticated', False):
            return False
        # Només el rol admin pur (is_staff sense is_superuser).
        # is_superuser residual ja ho cobreix User.has_perm (True per tot).
        if not getattr(user_obj, 'is_staff', False) or getattr(user_obj, 'is_superuser', False):
            return False
        return perm not in AUTH_USER_MGMT_WRITE_PERMS

    def has_module_perms(self, user_obj, app_label):
        if not getattr(user_obj, 'is_active', False):
            return False
        if not getattr(user_obj, 'is_authenticated', False):
            return False
        if not getattr(user_obj, 'is_staff', False) or getattr(user_obj, 'is_superuser', False):
            return False
        return True
