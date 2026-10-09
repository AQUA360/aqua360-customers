from django.core.management.base import BaseCommand, CommandError

from integrations.outbound.giswater.auth import (
    get_access_token,
    get_basic_auth,
    uses_keycloak,
)
from integrations.outbound.giswater.exceptions import GiswaterAuthError


def _mask(value: str, keep: int = 8) -> str:
    if not value:
        return ""
    if len(value) <= keep * 2:
        return "*" * len(value)
    return f"{value[:keep]}...{value[-keep:]}"


class Command(BaseCommand):
    help = (
        "Valida l'autenticació de Giswater: OAuth Keycloak si "
        "GISWATER_KEYCLOAK_URL està definit; altrament HTTP Basic Auth."
    )

    def handle(self, *args, **options):
        try:
            if uses_keycloak():
                token = get_access_token()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Autenticació Keycloak correcta. "
                        f"Token obtingut ({len(token)} caràcters)."
                    )
                )
                self.stdout.write(f"Token: {_mask(token)}")
                return

            auth = get_basic_auth()
            self.stdout.write(
                self.style.SUCCESS(
                    "Autenticació Basic Auth configurada correctament "
                    f"(usuari: {auth.username})."
                )
            )
            self.stdout.write(
                "GISWATER_KEYCLOAK_URL buit → s'usarà HTTP Basic Auth a les crides."
            )
        except GiswaterAuthError as exc:
            raise CommandError(str(exc)) from exc
