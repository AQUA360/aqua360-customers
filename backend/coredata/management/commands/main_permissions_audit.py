from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from coredata.models import MainPermission
from coredata.permission_catalog import EXCLUDED_MODELS, catalog_models


def project_models():
    """Models de les apps pròpies que tenen permisos de Django (view/add/change/delete)."""
    own = set(settings.OWN_APPS)
    return sorted(
        f'{model._meta.app_label}.{model._meta.model_name}'
        for model in apps.get_models()
        if apps.get_app_config(model._meta.app_label).name in own
        and not model._meta.auto_created
        and model._meta.default_permissions
    )


def assigned_models():
    """Models que algun MainPermission llista ara mateix a `affected_models`."""
    assigned = set()
    for affected in MainPermission.objects.values_list('affected_models', flat=True):
        assigned.update(piece.strip() for piece in (affected or '').split(',') if piece.strip())
    return assigned


class Command(BaseCommand):
    help = (
        "Llista els models del projecte que cap MainPermission governa i, per tant, no es poden "
        "donar a un grup des de la pantalla de permisos. Amb --fail acaba amb error si en queda "
        "algun sense bloc al catàleg (coredata/permission_catalog.py)."
    )

    def add_arguments(self, parser):
        parser.add_argument('--fail', action='store_true', help='Error si hi ha models sense bloc al catàleg.')

    def handle(self, *args, **options):
        catalog = catalog_models()
        assigned = assigned_models()
        models = project_models()

        sense_bloc = [m for m in models if m not in catalog and m not in assigned and m not in EXCLUDED_MODELS]
        pendents = [m for m in models if m in catalog and m not in assigned]
        obsolets = sorted(m for m in catalog if m not in models)
        existents = set(MainPermission.objects.values_list('name', flat=True))
        sense_main_permission = sorted({mp for mp in catalog.values() if mp not in existents})

        self.stdout.write(f'Models del projecte amb permisos: {len(models)}')
        self.stdout.write(f'Governats ara per algun MainPermission: {len([m for m in models if m in assigned])}')
        self.stdout.write(f'Al catàleg però encara no assignats a la BD (els aplica el script d\'operacions): {len(pendents)}')
        if sense_main_permission:
            self.stdout.write(f'MainPermission del catàleg que no existeixen en aquesta BD: {", ".join(sense_main_permission)}')
        if obsolets:
            self.stdout.write(f'Al catàleg però ja no existeixen com a model: {", ".join(obsolets)}')
        self.stdout.write(f'SENSE BLOC (cal afegir-los al catàleg): {len(sense_bloc)}')
        for model in sense_bloc:
            self.stdout.write(f'  {model}')

        if options['fail'] and sense_bloc:
            raise CommandError(f'{len(sense_bloc)} models sense bloc de permisos.')
