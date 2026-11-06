"""
Valors esperats del catàleg SendBatch i dels ConfigProject relacionats.

S'usen a la pantalla de configuració per detectar el que falta i crear-ho
amb els tokens canònics (Odoo + estats 0/1/2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from coredata.models import ConfigProject
from coredata.permissions import can_edit_config_project
from integrations.models import SendBatchProvider, SendBatchStatus, SendBatchType


@dataclass(frozen=True)
class ExpectedProvider:
    token: str
    name: str
    position: int
    is_default: bool = False


@dataclass(frozen=True)
class ExpectedType:
    token: str
    name: str
    endpoint: str
    position: int
    provider_token: str
    is_default: bool = False


@dataclass(frozen=True)
class ExpectedStatus:
    token: str
    name: str
    position: int
    color: Optional[str] = None
    is_default: bool = False


@dataclass(frozen=True)
class ExpectedConfigProject:
    token: str
    name: str
    value: str
    file: str = "General"


EXPECTED_PROVIDERS = (
    ExpectedProvider(token="odoo", name="Odoo", position=1, is_default=True),
)

EXPECTED_TYPES = (
    ExpectedType(
        token="invoices",
        name="Factures",
        endpoint="/batch/invoices",
        position=1,
        provider_token="odoo",
        is_default=True,
    ),
    ExpectedType(
        token="payments",
        name="Pagaments",
        endpoint="/batch/payments",
        position=2,
        provider_token="odoo",
    ),
    ExpectedType(
        token="commitment_create",
        name="Compromís (creació)",
        endpoint="/batch/commitment/create",
        position=3,
        provider_token="odoo",
    ),
    ExpectedType(
        token="commitment_cancel",
        name="Compromís (cancel·lació)",
        endpoint="/batch/commitment/cancel",
        position=4,
        provider_token="odoo",
    ),
)

EXPECTED_STATUSES = (
    ExpectedStatus(token="0", name="Pendent", position=1, is_default=True),
    ExpectedStatus(token="1", name="Processant", position=2, color="blue"),
    ExpectedStatus(token="2", name="Finalitzat", position=3, color="green"),
)

EXPECTED_CONFIG_PROJECTS = (
    ExpectedConfigProject(
        token="ODOO_ENABLED",
        name="Integració Odoo habilitada",
        value="true",
    ),
    ExpectedConfigProject(
        token="send_batch_status_pending_token",
        name="Token d'estat pendent d'un lot d'enviament (SendBatch)",
        value="0",
    ),
    ExpectedConfigProject(
        token="send_batch_status_processing_token",
        name="Token d'estat en procés d'un lot d'enviament (SendBatch)",
        value="1",
    ),
    ExpectedConfigProject(
        token="send_batch_status_finalized_token",
        name="Token d'estat finalitzat d'un lot d'enviament (SendBatch)",
        value="2",
    ),
)


def _serialize_provider(obj: SendBatchProvider) -> dict:
    return {
        "id": obj.id,
        "token": obj.token,
        "name": obj.name,
        "position": obj.position,
        "is_default": obj.is_default,
    }


def _serialize_type(obj: SendBatchType) -> dict:
    return {
        "id": obj.id,
        "token": obj.token,
        "name": obj.name,
        "endpoint": obj.endpoint,
        "position": obj.position,
        "is_default": obj.is_default,
        "provider_id": obj.provider_id,
        "provider": _serialize_provider(obj.provider) if obj.provider_id else None,
    }


def _serialize_status(obj: SendBatchStatus) -> dict:
    return {
        "id": obj.id,
        "token": obj.token,
        "name": obj.name,
        "color": obj.color,
        "position": obj.position,
        "is_default": obj.is_default,
    }


def _serialize_config(obj: ConfigProject) -> dict:
    return {
        "token": obj.token,
        "name": obj.name,
        "value": obj.value,
        "file": obj.file,
    }


def get_send_batch_settings_overview() -> dict:
    providers = list(SendBatchProvider.objects.all().order_by("position", "token"))
    types = list(
        SendBatchType.objects.select_related("provider").order_by(
            "provider__position", "position", "token"
        )
    )
    statuses = list(SendBatchStatus.objects.all().order_by("position", "token"))
    config_tokens = [item.token for item in EXPECTED_CONFIG_PROJECTS]
    configs = {
        item.token: item
        for item in ConfigProject.objects.filter(token__in=config_tokens)
    }

    missing_providers = [
        expected.token
        for expected in EXPECTED_PROVIDERS
        if not any(p.token == expected.token for p in providers)
    ]
    missing_types = [
        {"token": expected.token, "provider_token": expected.provider_token}
        for expected in EXPECTED_TYPES
        if not any(
            t.token == expected.token
            and t.provider
            and t.provider.token == expected.provider_token
            for t in types
        )
    ]
    missing_statuses = [
        expected.token
        for expected in EXPECTED_STATUSES
        if not any(s.token == expected.token for s in statuses)
    ]
    missing_configs = [
        expected.token
        for expected in EXPECTED_CONFIG_PROJECTS
        if expected.token not in configs
    ]

    return {
        "providers": [_serialize_provider(item) for item in providers],
        "types": [_serialize_type(item) for item in types],
        "statuses": [_serialize_status(item) for item in statuses],
        "config_projects": [
            (
                {**_serialize_config(configs[expected.token]), "missing": False}
                if expected.token in configs
                else {
                    "token": expected.token,
                    "name": expected.name,
                    "value": None,
                    "file": expected.file,
                    "missing": True,
                }
            )
            for expected in EXPECTED_CONFIG_PROJECTS
        ],
        "expected": {
            "providers": [expected.__dict__ for expected in EXPECTED_PROVIDERS],
            "types": [expected.__dict__ for expected in EXPECTED_TYPES],
            "statuses": [expected.__dict__ for expected in EXPECTED_STATUSES],
            "config_projects": [
                expected.__dict__ for expected in EXPECTED_CONFIG_PROJECTS
            ],
        },
        "missing": {
            "providers": missing_providers,
            "types": missing_types,
            "statuses": missing_statuses,
            "config_projects": missing_configs,
        },
        "has_missing": bool(
            missing_providers
            or missing_types
            or missing_statuses
            or missing_configs
        ),
    }


def ensure_send_batch_defaults(*, user=None) -> dict:
    """
    Crea els registres esperats si no existeixen.

    No sobreescriu valors ja presents (només omple el que falta).
    Els ConfigProject només es creen si l'usuari pot editar ConfigProject.
    """
    created = {
        "providers": [],
        "types": [],
        "statuses": [],
        "config_projects": [],
    }
    skipped_configs = []

    provider_by_token = {
        item.token: item for item in SendBatchProvider.objects.all()
    }
    for expected in EXPECTED_PROVIDERS:
        if expected.token in provider_by_token:
            continue
        if expected.is_default:
            SendBatchProvider.objects.filter(is_default=True).update(is_default=False)
        provider = SendBatchProvider.objects.create(
            token=expected.token,
            name=expected.name,
            position=expected.position,
            is_default=expected.is_default,
        )
        provider_by_token[provider.token] = provider
        created["providers"].append(_serialize_provider(provider))

    existing_types = {
        (item.provider.token, item.token): item
        for item in SendBatchType.objects.select_related("provider")
    }
    for expected in EXPECTED_TYPES:
        key = (expected.provider_token, expected.token)
        if key in existing_types:
            continue
        provider = provider_by_token.get(expected.provider_token)
        if provider is None:
            continue
        if expected.is_default:
            SendBatchType.objects.filter(provider=provider, is_default=True).update(
                is_default=False
            )
        batch_type = SendBatchType.objects.create(
            provider=provider,
            token=expected.token,
            name=expected.name,
            endpoint=expected.endpoint,
            position=expected.position,
            is_default=expected.is_default,
        )
        existing_types[key] = batch_type
        created["types"].append(_serialize_type(batch_type))

    existing_statuses = {
        item.token: item for item in SendBatchStatus.objects.all()
    }
    for expected in EXPECTED_STATUSES:
        if expected.token in existing_statuses:
            continue
        if expected.is_default:
            SendBatchStatus.objects.filter(is_default=True).update(is_default=False)
        status_obj = SendBatchStatus.objects.create(
            token=expected.token,
            name=expected.name,
            color=expected.color,
            position=expected.position,
            is_default=expected.is_default,
        )
        existing_statuses[status_obj.token] = status_obj
        created["statuses"].append(_serialize_status(status_obj))

    can_write_config = can_edit_config_project(user) if user is not None else False
    for expected in EXPECTED_CONFIG_PROJECTS:
        if ConfigProject.objects.filter(token=expected.token).exists():
            continue
        if not can_write_config:
            skipped_configs.append(expected.token)
            continue
        config = ConfigProject.objects.create(
            token=expected.token,
            name=expected.name,
            value=expected.value,
            file=expected.file,
        )
        created["config_projects"].append(_serialize_config(config))

    overview = get_send_batch_settings_overview()
    return {
        "created": created,
        "skipped_config_projects": skipped_configs,
        "overview": overview,
    }
