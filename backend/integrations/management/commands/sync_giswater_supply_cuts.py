from django.core.management.base import BaseCommand, CommandError

from integrations.outbound.giswater.exceptions import GiswaterApiError
from integrations.outbound.giswater.sync import sync_supply_cuts_from_giswater


class Command(BaseCommand):
    help = (
        "Sincronitza SupplyCut des de Giswater (mincuts): "
        "causes, estats, mincuts i punts de subministrament afectats."
    )

    def handle(self, *args, **options):
        self.stdout.write("Sincronitzant mincuts de Giswater…")
        try:
            stats = sync_supply_cuts_from_giswater()
        except GiswaterApiError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS("Sincronització de mincuts completada"))
        for key in ("total_fields", "causes_created", "statuses_created"):
            self.stdout.write(f"  {key}: {stats.get(key, 0)}")
