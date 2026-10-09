from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from typing import Optional

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

CONNEC_TYPE_ESCO = "ESCO"

def extract_fields(response: dict) -> list[dict]:
    body = response.get("body") or {}
    data = body.get("data") or {}
    return data.get("fields") or []

def extract_connec_fields(response: dict) -> list[dict]:
    return extract_fields(response)

def filter_esco_connecs(fields: list[dict]) -> list[dict]:
    return [
        field
        for field in fields
        if field.get("connec_type") == CONNEC_TYPE_ESCO
    ]


def map_connec_to_connection_values(connec: dict) -> Optional[dict]:
    customer_code = connec.get("customer_code")
    connec_id = connec.get("connec_id")

    if customer_code in (None, ""):
        return None
    if connec_id in (None, ""):
        return None

    return {
        "customer_code": str(customer_code).strip(),
        "code_gis": str(connec_id),
        "latitude": to_decimal(connec.get("lat")),
        "longitude": to_decimal(connec.get("long")),
    }


def to_aware_datetime(value) -> Optional[datetime]:
    """Normalitza una data de Giswater per guardar-la en un DateTimeField.

    Si ja és aware (porta Z o offset) es deixa. Si és naive (el cas habitual
    de Giswater) i USE_TZ està actiu, es fa make_aware amb TIME_ZONE.
    Valors buits o il·legibles queden a None i no bloquegen la sync.
    """
    if value in (None, ""):
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        dt = parse_datetime(text)
        if dt is None:
            parsed_date = parse_date(text)
            if parsed_date is None:
                return None
            dt = datetime.combine(parsed_date, time.min)

    if timezone.is_aware(dt):
        return dt
    if not timezone.get_current_timezone():
        return dt
    return timezone.make_aware(dt)


def map_mincut_to_supply_cut_dates(mincut: dict) -> dict:
    """Separa previsió i execució. `received_date` no és cap de les dues."""
    return {
        "date_start": to_aware_datetime(mincut.get("forecast_start")),
        "date_end": to_aware_datetime(mincut.get("forecast_end")),
        "exec_start": to_aware_datetime(mincut.get("exec_start")),
        "exec_end": to_aware_datetime(mincut.get("exec_end")),
    }


def to_decimal(value) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.000001"))
    except (InvalidOperation, ValueError, TypeError):
        return None


def build_connection_updates_by_token(fields: list[dict]) -> tuple[dict[str, dict], int]:
    updates_by_token: dict[str, dict] = {}
    skipped = 0

    for connec in filter_esco_connecs(fields):
        mapped = map_connec_to_connection_values(connec)
        if not mapped:
            skipped += 1
            continue
        updates_by_token[mapped["customer_code"]] = {
            "code_gis": mapped["code_gis"],
            "latitude": mapped["latitude"],
            "longitude": mapped["longitude"],
        }

    return updates_by_token, skipped
