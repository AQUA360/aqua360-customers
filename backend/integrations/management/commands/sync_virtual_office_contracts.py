from django.core.management.base import BaseCommand, CommandError

from integrations.outbound.ov.exceptions import OVApiError
from integrations.outbound.ov.sync import sync_virtual_office_contracts


class Command(BaseCommand):
    help = "Posa al dia la data d'alta a l'oficina virtual dels contractes amb la llista de l'OV."

    def handle(self, *args, **options):
        try:
            stats = sync_virtual_office_contracts()
        except OVApiError as exc:
            raise CommandError(str(exc)) from exc

        for key in ("ov_contracts", "registered", "updated", "unregistered", "unchanged", "errors"):
            self.stdout.write(f"  {key}: {stats[key]}")
        not_found = stats["not_found_tokens"]
        if not_found:
            self.stdout.write(self.style.WARNING(f"Contractes de l'OV que no són al Customers ({len(not_found)}):"))
            for token in not_found:
                self.stdout.write(f"  {token}")

        if stats["errors"]:
            raise CommandError(
                f"{stats['errors']} contractes no s'han pogut desar (detall al log); la resta s'han sincronitzat."
            )
        self.stdout.write(self.style.SUCCESS("Sincronització completada"))
