"""
Registre de proveïdors per a l'API genèrica de SendBatch.

El ViewSet no importa clients concrets: resol el servei a partir de
`batch.batch_type.provider.token` (amb alias via ConfigProject per Odoo).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from coredata.models import ConfigProject
from integrations.models import SendBatch


class SendBatchProviderError(Exception):
    """Proveïdor desconegut o lot sense provider assignat."""


@dataclass(frozen=True)
class SendBatchProviderService:
    """Contracte que ha d'exposar cada integració outbound de lots."""

    api_error: type[Exception]
    mapping_error: type[Exception]
    retry_send_batch: Callable
    check_batch_status: Callable
    build_send_payload_preview: Callable
    push_invoice_batch: Callable
    push_payment_movement_batch: Callable
    push_commitment_deposit_batch: Callable


def _build_odoo_service() -> SendBatchProviderService:
    from integrations.outbound.odoo.exceptions import OdooApiError, OdooMappingError
    from integrations.outbound.odoo import services as odoo_services

    return SendBatchProviderService(
        api_error=OdooApiError,
        mapping_error=OdooMappingError,
        retry_send_batch=odoo_services.retry_send_batch,
        check_batch_status=odoo_services.check_batch_status,
        build_send_payload_preview=odoo_services.build_send_payload_preview,
        push_invoice_batch=odoo_services.push_invoice_batch,
        push_payment_movement_batch=odoo_services.push_payment_movement_batch,
        push_commitment_deposit_batch=odoo_services.push_commitment_deposit_batch,
    )


# token de SendBatchProvider → factory del servei
_PROVIDER_FACTORIES: dict[str, Callable[[], SendBatchProviderService]] = {
    "odoo": _build_odoo_service,
}


def register_send_batch_provider(
    token: str, factory: Callable[[], SendBatchProviderService]
) -> None:
    """Permet registrar un proveïdor addicional (tests o noves integracions)."""
    _PROVIDER_FACTORIES[token] = factory


def _odoo_configured_token() -> str:
    try:
        return ConfigProject.objects.get(token="send_batch_provider_odoo_token").value
    except ConfigProject.DoesNotExist:
        return "odoo"


def get_provider_token(batch: SendBatch) -> str:
    if not batch.batch_type_id:
        raise SendBatchProviderError("El lot no té tipus assignat.")
    batch_type = batch.batch_type
    if not batch_type.provider_id:
        raise SendBatchProviderError(
            f"El tipus de lot {batch_type.token!r} no té provider assignat."
        )
    return batch_type.provider.token


def get_send_batch_service(batch: SendBatch) -> SendBatchProviderService:
    """
    Resol el servei outbound del lot.

    1. token exacte al registre
    2. si el token coincideix amb ConfigProject send_batch_provider_odoo_token → Odoo
    """
    token = get_provider_token(batch)
    factory = _PROVIDER_FACTORIES.get(token)
    if factory is None and token == _odoo_configured_token():
        factory = _PROVIDER_FACTORIES.get("odoo")
    if factory is None:
        raise SendBatchProviderError(
            f"No hi ha servei configurat per al provider {token!r}."
        )
    return factory()
