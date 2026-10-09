import importlib
import pkgutil

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction

from coredata.models import ExecutedScript

OPSCRIPTS_PACKAGE = "opscripts"


class Command(BaseCommand):
    help = (
        "Runs one-off maintenance/data scripts placed in <app>/opscripts/000N_name.py, "
        "in order, once per environment. Independent from Django migrations: use this for "
        "data backfills, fixes, or admin tasks that should run automatically on deploy "
        "instead of being launched by hand."
    )

    def handle(self, *args, **options):
        for app_config in apps.get_app_configs():
            try:
                package = importlib.import_module(f"{app_config.name}.{OPSCRIPTS_PACKAGE}")
            except ModuleNotFoundError:
                continue

            module_names = sorted(
                name for _, name, is_pkg in pkgutil.iter_modules(package.__path__)
                if not is_pkg and not name.startswith("_")
            )
            for module_name in module_names:
                self._run_script(app_config.label, package.__name__, module_name)

    def _run_script(self, app_label, package_name, module_name):
        if ExecutedScript.objects.filter(app_label=app_label, name=module_name).exists():
            return

        module = importlib.import_module(f"{package_name}.{module_name}")
        run = getattr(module, "run", None)
        if run is None:
            self.stderr.write(self.style.ERROR(
                f"Skipping {app_label}.{module_name}: no run() function defined."
            ))
            return

        self.stdout.write(f"Running {app_label}.{module_name}...")
        with transaction.atomic():
            run()
            ExecutedScript.objects.create(app_label=app_label, name=module_name)
        self.stdout.write(self.style.SUCCESS(f"Done: {app_label}.{module_name}"))
