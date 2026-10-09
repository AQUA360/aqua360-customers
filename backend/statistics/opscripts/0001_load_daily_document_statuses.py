"""Load DailyDocumentStatus rows and their ConfigProject token mappings.

Picks Catalan (`initial_data/ca`) or Spanish (`initial_data/es`) fixtures from
`settings.LANGUAGE`, then upserts by token so it is safe if some rows already
exist from `loaddata` or migration 0132.
"""
import json

from django.conf import settings
from django.core.management.color import color_style

from coredata.models import ConfigProject
from statistics.models import DailyDocumentStatus

style = color_style()

DAILY_DOCUMENT_CONFIG_TOKENS = (
    "daily_document_status_pending_token",
    "daily_document_status_completed_token",
    "daily_document_status_cancelled_token",
    "daily_document_status_expired_token",
)

STATUS_FIXTURE_NAME = "statistics.DailyDocumentStatus.json"
CONFIG_FIXTURE_RELATIVE = ("config_project", "local", "ConfigProject.json")


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


def _load_daily_document_statuses(data_dir):
    fixture_path = data_dir / STATUS_FIXTURE_NAME
    created = updated = 0

    for entry in _load_json(fixture_path):
        fields = entry.get("fields") or {}
        token = fields.get("token")
        if not token:
            continue
        defaults = _model_defaults(DailyDocumentStatus, fields)
        _, was_created = DailyDocumentStatus.objects.update_or_create(
            token=token,
            defaults=defaults,
        )
        if was_created:
            created += 1
        else:
            updated += 1

    print(style.SUCCESS(
        f"DailyDocumentStatus from {fixture_path}: {created} created, {updated} updated"
    ))


def _load_daily_document_config(data_dir):
    fixture_path = data_dir.joinpath(*CONFIG_FIXTURE_RELATIVE)
    wanted = set(DAILY_DOCUMENT_CONFIG_TOKENS)
    created = updated = 0

    for entry in _load_json(fixture_path):
        fields = entry.get("fields") or {}
        token = fields.get("token")
        if token not in wanted:
            continue
        defaults = _model_defaults(ConfigProject, fields)
        _, was_created = ConfigProject.objects.update_or_create(
            token=token,
            defaults=defaults,
        )
        if was_created:
            created += 1
        else:
            updated += 1
        wanted.discard(token)

    if wanted:
        raise ValueError(
            f"Missing daily document ConfigProject tokens in {fixture_path}: "
            + ", ".join(sorted(wanted))
        )

    print(style.SUCCESS(
        f"ConfigProject daily document tokens from {fixture_path}: "
        f"{created} created, {updated} updated"
    ))


def run():
    language = _language()
    data_dir = _data_dir()
    print(f"Loading daily document statuses for LANGUAGE={language} ({data_dir})")
    _load_daily_document_statuses(data_dir)
    _load_daily_document_config(data_dir)
