"""Load the default cluster (battery) documentation types, e.g. "Fotos".

Picks Catalan (`initial_data/ca`) or Spanish (`initial_data/es`) fixtures from
`settings.LANGUAGE` and creates only the tokens that do not exist yet, so rows
already loaded or edited by the client are left untouched.
"""
import json

from django.conf import settings
from django.core.management.color import color_style

from service.models import ClusterDocumentationType

style = color_style()

FIXTURE_NAME = "service.ClusterDocumentationType.json"


def _language():
    language = getattr(settings, "LANGUAGE", None) or getattr(settings, "LANGUAGE_CODE", None) or "ca"
    language = str(language).lower().replace("_", "-")
    if language == "es" or language.startswith("es-"):
        return "es"
    return "ca"


def run():
    data_dir = settings.BASE_DIR / "initial_data" / _language()
    with open(data_dir / FIXTURE_NAME, encoding="utf-8") as fixture_file:
        entries = json.load(fixture_file)
    created = 0
    for entry in entries:
        fields = entry["fields"]
        _, was_created = ClusterDocumentationType.objects.get_or_create(
            token=fields["token"],
            defaults={
                "name": fields["name"],
                "position": fields["position"],
                "is_default": fields["is_default"],
                "is_active": fields["is_active"],
            },
        )
        created += int(was_created)
    print(style.SUCCESS(f"ClusterDocumentationType from {data_dir / FIXTURE_NAME}: {created} created"))
