"""
Sincronització dels contractes que tenen l'oficina virtual activa.

L'OV exposa un GET (`OV_ACTIVE_CONTRACTS_ENDPOINT`) amb els contractes vinculats a
algun usuari, un element per vinculació:

    [{"contract_number": "<token>", "user_email": "...",
      "user_registration_date": "2026-10-16T10:57:29Z",
      "contract_link_date": "2026-11-16T07:06:50.793511Z"}, ...]

`contract_number` és el `Contract.token` i la data d'alta és la de vinculació del
contracte (si en té diverses, la més antiga). Del correu de l'usuari no se'n desa res.

Per a cada contracte actiu del Customers:
- és a la llista i no tenia data → alta: `virtual_office_date` = data de vinculació (o avui);
- és a la llista amb una data diferent → es posa la de l'OV;
- no hi és i tenia data → baixa: `virtual_office_date` = None.

Es desa amb `update()` i s'apunta a l'historial (ContractLog) com a procés automàtic,
sense disparar els senyals del contracte (vegeu `write_virtual_office_date`).
"""

import logging
import uuid

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from contract.models import Contract, ContractLog

from .client import OVClient
from .exceptions import OVApiError

logger = logging.getLogger(__name__)


def is_ov_sync_enabled():
    return bool(settings.OV_SYNC_ENABLED and settings.OV_API_BASE_URL)


def parse_link_date(value):
    """Data local d'un datetime ISO de l'OV (UTC) o d'una data sola; None si no és vàlid."""
    if not value:
        return None
    text = str(value).strip()
    try:
        moment = parse_datetime(text)
        if moment is not None:
            return timezone.localdate(moment) if timezone.is_aware(moment) else moment.date()
        return parse_date(text)
    except ValueError:
        return None


def extract_active_contracts(data):
    """{token: data d'alta o None} a partir de la resposta de l'OV."""
    if not isinstance(data, list):
        raise OVApiError("La resposta de l'oficina virtual no és una llista de contractes")

    active = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        token = str(item.get("contract_number") or "").strip()
        if not token:
            continue
        link_date = parse_link_date(item.get("contract_link_date"))
        current = active.get(token)
        if token not in active or (link_date and (current is None or link_date < current)):
            active[token] = link_date
    return active


def write_virtual_office_date(contract_id, target):
    """Desa la data i la deixa a l'historial sense passar pels senyals del contracte.

    Amb `save()` saltarien tots els senyals de Contract, i n'hi ha que fan feina de
    negoci en cada desament (p. ex. el d'un contracte de baixa retorna les fiances
    pendents i en genera la factura): una sincronització no ha de disparar-los.
    """
    contract = Contract.objects.select_for_update().only("id", "virtual_office_date").get(pk=contract_id)
    previous = contract.virtual_office_date
    if previous == target:
        return False
    Contract.objects.filter(pk=contract_id).update(virtual_office_date=target, updated_at=timezone.now())
    ContractLog.objects.create(
        contract_id=contract_id,
        field_name="virtual_office_date",
        old_value=str(previous) if previous is not None else None,
        new_value=str(target) if target is not None else None,
        operation_token=str(uuid.uuid4()),
        user=None,
    )
    return True


def sync_virtual_office_contracts(data=None):
    if data is None:
        data = OVClient().get_active_contracts()
    active = extract_active_contracts(data)

    contracts = Contract.objects.filter(is_active=True).filter(
        Q(token__in=active.keys()) | Q(virtual_office_date__isnull=False)
    )
    if not active and contracts.exists():
        # Una llista buida donaria de baixa tots els contractes: més aviat és un error de l'OV.
        raise OVApiError("L'oficina virtual no ha retornat cap contracte; no es dona de baixa cap contracte")

    stats = {"ov_contracts": len(active), "registered": 0, "updated": 0, "unregistered": 0, "unchanged": 0, "errors": 0, "not_found_tokens": []}
    today = timezone.localdate()
    found_tokens = set()

    for contract in contracts.only("id", "token", "virtual_office_date"):
        found_tokens.add(contract.token)
        if contract.token in active:
            target = active[contract.token] or contract.virtual_office_date or today
        else:
            target = None

        if target == contract.virtual_office_date:
            stats["unchanged"] += 1
            continue

        if target is None:
            key = "unregistered"
        elif contract.virtual_office_date is None:
            key = "registered"
        else:
            key = "updated"
        try:
            with transaction.atomic():
                written = write_virtual_office_date(contract.pk, target)
        except Exception:
            logger.exception("Error desant l'alta a l'oficina virtual del contracte %s", contract.pk)
            stats["errors"] += 1
            continue
        stats[key if written else "unchanged"] += 1

    stats["not_found_tokens"] = sorted(set(active) - found_tokens)
    return stats
