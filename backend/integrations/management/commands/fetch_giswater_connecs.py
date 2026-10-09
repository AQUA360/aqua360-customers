import json

from django.core.management.base import BaseCommand, CommandError

from integrations.models import IntegrationRequestLog
from integrations.outbound.giswater.client import GET_LIST_ENDPOINT, PROVIDER
from integrations.outbound.giswater.exceptions import GiswaterApiError
from integrations.outbound.giswater.services import fetch_connecs


def _summarize_response(data):
    if isinstance(data, list):
        return len(data), "registres"

    if isinstance(data, dict):
        for key in ("data", "results", "rows", "features", "list"):
            value = data.get(key)
            if isinstance(value, list):
                return len(value), key

    return None, None


def _preview(data, limit=500):
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n... (resposta truncada, veure log complet)"


class Command(BaseCommand):
    help = (
        "Obté la llista de connecs de Giswater (ve_connec) i registra la resposta "
        "a IntegrationRequestLog."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--save-json",
            dest="save_json",
            default="",
            help="Ruta opcional per guardar la resposta JSON completa en un fitxer.",
        )
        parser.add_argument(
            "--preview-chars",
            dest="preview_chars",
            type=int,
            default=500,
            help="Caràcters de previsualització a mostrar per consola (default: 500).",
        )

    def handle(self, *args, **options):
        try:
            data = fetch_connecs()
        except GiswaterApiError as exc:
            log = (
                IntegrationRequestLog.objects.filter(
                    provider=PROVIDER,
                    endpoint=GET_LIST_ENDPOINT,
                )
                .order_by("-created_at")
                .first()
            )
            if log:
                self.stdout.write(
                    self.style.WARNING(
                        f"Log d'error creat (id={log.id}): {log.error_message}"
                    )
                )
            raise CommandError(str(exc)) from exc

        log = (
            IntegrationRequestLog.objects.filter(
                provider=PROVIDER,
                endpoint=GET_LIST_ENDPOINT,
                success=True,
            )
            .order_by("-created_at")
            .first()
        )

        count, key = _summarize_response(data)
        if count is not None:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Connecs obtingudes correctament: {count} elements"
                    + (f" a '{key}'" if key != "registres" else "")
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("Connecs obtingudes correctament."))

        if log:
            self.stdout.write(
                f"Resposta guardada a IntegrationRequestLog (id={log.id}, "
                f"status_code={log.status_code})"
            )
            self.stdout.write(
                "Pots consultar-la des de l'admin Django: "
                "Integrations → Integration request logs"
            )

        save_json = options["save_json"]
        if save_json:
            with open(save_json, "w", encoding="utf-8") as output_file:
                json.dump(data, output_file, ensure_ascii=False, indent=2)
            self.stdout.write(f"JSON guardat a: {save_json}")

        self.stdout.write("\nPrevisualització de la resposta:")
        self.stdout.write(
            _preview(data, limit=options["preview_chars"])
        )
