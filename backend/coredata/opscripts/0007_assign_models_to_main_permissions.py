"""Associa a un MainPermission els models que havien quedat sense cap (coredata/permission_catalog.py).

Fa dues coses per cada bloc del catàleg que existeix a la BD:

1. Afegeix a `affected_models` els models que hi falten.
2. Als grups que ja tenen aquest bloc (tenen el permís de veure algun dels models que ja hi
   eren i que no són també d'un altre bloc) els dona també veure els models nous; i, si ja podien modificar algun dels que hi
   eren, també afegir/modificar/esborrar-los. Sense això, els grups només ho rebrien en tornar
   a desar-se des de la pantalla de grups i, en restringir les vistes, perdrien accés.

El bloc `users` (change_requires_superuser) mai dona escriptura als grups. Els grups que no
tenien el bloc no reben res. No es toca res dels superusuaris (ja ho poden tot).
"""

from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.db.models import Q


def _permissions(models, prefixes):
    query = Q()
    for model in models:
        app_label, model_name = model.split('.')
        query |= Q(
            content_type__app_label=app_label,
            content_type__model=model_name,
            codename__in=[f'{prefix}_{model_name}' for prefix in prefixes],
        )
    return Permission.objects.filter(query) if query else Permission.objects.none()


def _model_exists(model):
    try:
        apps.get_model(*model.split('.'))
        return True
    except LookupError:
        return False


def run():
    from coredata.models import MainPermission
    from coredata.permission_catalog import MAIN_PERMISSION_MODELS

    through = Group.permissions.through

    for name, catalog_models in MAIN_PERMISSION_MODELS.items():
        main_permission = MainPermission.objects.filter(name=name).first()
        if main_permission is None:
            print(f'[main_permissions] el bloc {name} no existeix en aquesta BD: s\'omet')
            continue

        current = [m.strip() for m in (main_permission.affected_models or '').split(',') if m.strip()]
        new = [m for m in catalog_models if m not in current and _model_exists(m)]
        if not new:
            continue

        # Un model pot ser a dos blocs (fraud.fraud, notification.incident): per saber si un grup té
        # aquest bloc només mirem els models que són exclusivament seus.
        in_other_blocks = set()
        for affected in MainPermission.objects.exclude(pk=main_permission.pk).values_list('affected_models', flat=True):
            in_other_blocks.update(m.strip() for m in (affected or '').split(',') if m.strip())
        exclusive = [m for m in current if m not in in_other_blocks] or current

        # Grups que ja tenen el bloc: abans de canviar res, mirem què poden fer sobre els seus models
        can_view = set(
            Group.objects.filter(permissions__in=_permissions(exclusive, ['view'])).values_list('id', flat=True)
        )
        can_change = set(
            Group.objects.filter(permissions__in=_permissions(exclusive, ['change'])).values_list('id', flat=True)
        )
        if main_permission.change_requires_superuser:
            can_change = set()

        links = []
        for permission in _permissions(new, ['view']):
            links += [through(group_id=group_id, permission_id=permission.id) for group_id in can_view]
        for permission in _permissions(new, ['add', 'change', 'delete']):
            links += [through(group_id=group_id, permission_id=permission.id) for group_id in can_change]
        through.objects.bulk_create(links, ignore_conflicts=True)

        main_permission.affected_models = ','.join(current + new)
        main_permission.save(update_fields=['affected_models', 'updated_at'])
        print(
            f'[main_permissions] {name}: +{len(new)} models; '
            f'{len(can_view)} grups amb lectura, {len(can_change)} amb escriptura'
        )
