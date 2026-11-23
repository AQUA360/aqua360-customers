"""Revoca permisos d'escriptura de gestió d'usuaris/grups a tots els no-superusuaris.

Només el superusuari pot crear/editar/eliminar usuaris i grups o canviar
contrasenyes. Es treuen add/change/delete de auth.user, auth.group i
auth.permission de tots els grups i dels user_permissions dels no-superusuaris.
També marca MainPermission `users` amb change_requires_superuser=True.
"""


USER_MGMT_MODELS = ('user', 'group', 'permission')
WRITE_ACTIONS = ('add', 'change', 'delete')


def run():
    from django.contrib.auth.models import Group, Permission, User
    from django.contrib.contenttypes.models import ContentType

    from coredata.models import MainPermission

    MainPermission.objects.filter(name='users').update(change_requires_superuser=True)

    content_types = ContentType.objects.filter(app_label='auth', model__in=USER_MGMT_MODELS)
    codenames = [
        f'{action}_{model}'
        for model in USER_MGMT_MODELS
        for action in WRITE_ACTIONS
    ]
    write_perms = list(
        Permission.objects.filter(content_type__in=content_types, codename__in=codenames)
    )
    if not write_perms:
        return

    for group in Group.objects.all().iterator():
        group.permissions.remove(*write_perms)

    for user in User.objects.filter(is_superuser=False).iterator():
        user.user_permissions.remove(*write_perms)
