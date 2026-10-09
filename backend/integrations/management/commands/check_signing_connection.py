from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from documentmanager.utils.document_sign_config import is_document_sign_enabled
from integrations.outbound.signing.client import SigningClient
from integrations.outbound.signing.exceptions import SigningApiError


def _mask(value, keep=4):
    if not value:
        return "(buit)"
    if len(value) <= keep * 2:
        return "*" * len(value)
    return f"{value[:keep]}…{value[-keep:]} ({len(value)} caràcters)"


class Command(BaseCommand):
    help = (
        "Comprova la connexió outbound amb Aqua360 Sign: que SIGNING_BASE_URL "
        "respon i que SIGNING_API_KEY és acceptada. No crea cap sessió ni envia "
        "cap correu."
    )

    def handle(self, *args, **options):
        base_url = (settings.SIGNING_BASE_URL or "").rstrip("/")
        callback_url = settings.SIGNING_CALLBACK_URL or ""
        callback_key = settings.SIGN_CALLBACK_API_KEY or ""
        poll_enabled = bool(getattr(settings, "SIGNING_POLL_ENABLED", False))

        self.stdout.write(f"SIGNING_BASE_URL:      {base_url or '(buit)'}")
        self.stdout.write(f"SIGNING_API_KEY:       {_mask(settings.SIGNING_API_KEY or '')}")
        self.stdout.write(f"SIGNING_CALLBACK_URL:  {callback_url or '(buit)'}")
        self.stdout.write(
            "SIGN_CALLBACK_API_KEY: "
            + ("configurada " + _mask(callback_key) if callback_key else "(buit; el webhook no valida la clau)")
        )
        self.stdout.write(f"SIGNING_POLL_ENABLED:  {poll_enabled}")
        self.stdout.write(f"DOCUMENT_SIGN_ENABLED: {is_document_sign_enabled()}")
        self.stdout.write("")

        if not callback_url:
            self.stdout.write(
                self.style.WARNING(
                    "SIGNING_CALLBACK_URL és buit: en crear una sessió caldrà passar callback_url."
                )
            )
        if not poll_enabled:
            self.stdout.write(
                self.style.WARNING(
                    "SIGNING_POLL_ENABLED és False: el PDF firmat només torna si Sign "
                    "pot fer POST a SIGNING_CALLBACK_URL."
                )
            )

        try:
            SigningClient().check_connection()
        except SigningApiError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Connexió correcta. Sign ha autenticat la clau "
                "(HTTP 404: la sessió de prova no existeix, com és d'esperar)."
            )
        )
