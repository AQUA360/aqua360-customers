import json
import os

from coredata.models import ConfigProject

DEFAULT_CONFIG_PROJECT_FIXTURE_RELATIVE_PATH = os.path.join(
    "initial_data",
    "ca",
    "config_project",
    "local",
    "ConfigProject.json",
)

WATCHDOG_FIX_CONFIG_PROJECT_COMMAND = (
    "python manage.py watchdog_fix_config_project --dry-run\n"
    "  python manage.py watchdog_fix_config_project"
)


def get_project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_config_project_fixture_path():
    return os.path.join(get_project_root(), DEFAULT_CONFIG_PROJECT_FIXTURE_RELATIVE_PATH)


def load_config_project_fixture_entries(fixture_path=None):
    json_path = fixture_path or get_config_project_fixture_path()

    try:
        with open(json_path, "r", encoding="utf-8") as fixture_file:
            json_data = json.load(fixture_file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"JSON fixture file not found at: {json_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Error parsing JSON file: {exc}") from exc

    entries = []
    for entry in json_data:
        fields = entry.get("fields", {})
        token = fields.get("token")
        if not token:
            continue
        entries.append({
            "token": token,
            "name": fields.get("name"),
            "value": fields.get("value"),
            "file": fields.get("file"),
        })

    return entries


def get_missing_config_project_entries(tokens=None, fixture_path=None):
    entries = load_config_project_fixture_entries(fixture_path=fixture_path)

    if tokens is not None:
        token_set = set(tokens)
        entries = [entry for entry in entries if entry["token"] in token_set]

    missing_entries = []
    for entry in entries:
        if not ConfigProject.objects.filter(token=entry["token"]).exists():
            missing_entries.append(entry)

    return missing_entries


def create_missing_config_projects(missing_entries, dry_run=False):
    created_entries = []

    for entry in missing_entries:
        if dry_run:
            created_entries.append(entry)
            continue

        ConfigProject.objects.create(
            token=entry["token"],
            name=entry["name"],
            value=entry["value"],
            file=entry["file"],
        )
        created_entries.append(entry)

    return created_entries
