"""Load DailyDocumentSubmissionStatus rows from language fixtures.

Picks Catalan (`initial_data/ca`) or Spanish (`initial_data/es`) fixtures from
`settings.LANGUAGE`, then upserts by token so it is safe to re-run.
"""
import json

from django.conf import settings
from django.core.management.color import color_style

from statistics.models import DailyDocumentSubmissionStatus

style = color_style()

STATUS_FIXTURE_NAME = "statistics.DailyDocumentSubmissionStatus.json"


def _language():
    language = getattr(settings, "LANGUAGE", None) or getattr(settings, "LANGUAGE_CODE", None) or "ca"
    language = str(language).lower().replace("_", "-")
    if language == "es" or language.startswith("es-"):
        return "es"
    return "ca"


def _data_dir():
    return settings.BASE_DIR / "initial_data" / _language()


def _load_json(path):
    if not path.exists():
        raise FileNotFoundError(f"Fixture not found: {path}")
    with open(path, encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def _model_defaults(model, fields):
    skip = {"id", "pk", "created_at", "updated_at"}
    allowed = {field.name for field in model._meta.fields if field.name not in skip}
    return {key: value for key, value in fields.items() if key in allowed}


def run():
    language = _language()
    data_dir = _data_dir()
    fixture_path = data_dir / STATUS_FIXTURE_NAME
    print(f"Loading daily document submission statuses for LANGUAGE={language} ({fixture_path})")

    created = updated = 0
    for entry in _load_json(fixture_path):
        fields = entry.get("fields") or {}
        token = fields.get("token")
        if not token:
            continue
        defaults = _model_defaults(DailyDocumentSubmissionStatus, fields)
        _, was_created = DailyDocumentSubmissionStatus.objects.update_or_create(
            token=token,
            defaults=defaults,
        )
        if was_created:
            created += 1
        else:
            updated += 1

    print(style.SUCCESS(
        f"DailyDocumentSubmissionStatus from {fixture_path}: {created} created, {updated} updated"
    ))
