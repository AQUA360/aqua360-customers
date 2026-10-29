
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from decimal import Decimal, InvalidOperation
from typing import Any

from io import BytesIO

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Prefetch, Q
from django.utils import timezone

from billing.models import Reading, ReadingBatch, ReadingDocument
from billing.utils.reading_service import check_billing_period, check_overflow_value
from contract.models import Contract
from coredata.models import ConfigProject
from coredata.utils.address_utils import get_address_complete_without_city
from integrations.models import IntegrationRequestLog
from service.models import Route, RouteZone, SupplyPoint

logger = logging.getLogger(__name__)

PROVIDER = "smart_metering"
ORIGIN_SMART_METERING = "SMART METERING"
SMART_METERING_AUTH_CONFIG_TOKEN = "smart_metering_authentication_token"
SMART_METERING_EXPLOITATION_CONFIG_TOKEN = "smart_metering_explotation_id"
# Preview runs in Celery; allow a longer wait for the massive external API.
SMART_METERING_PREVIEW_API_TIMEOUT = 120
# Settings-page probe: a short reachability check, and a capped sample of a day's readings.
SMART_METERING_CONNECTIVITY_TIMEOUT = 10
SMART_METERING_PROBE_SAMPLE_LIMIT = 20
SMART_METERING_PROBE_DETAIL_LIMIT = 500
SMART_METERING_INBOUND_CONTRACTS_PATH = "/smartmetering/v1/contracts/"


class SmartMeteringApiError(Exception):
    pass


class SmartMeteringPreviewOutdated(ValueError):
    """The preview has rows outside the selected routes, zones or batches."""


def _response_payload_for_log(data):
    """Avoid storing huge massive-readings payloads in IntegrationRequestLog."""
    if isinstance(data, list):
        return {"count": len(data), "sample": data[:3]}
    if isinstance(data, dict):
        for key in ("results", "readings", "data"):
            value = data.get(key)
            if isinstance(value, list):
                summary = {k: v for k, v in data.items() if k != key}
                summary[key] = {"count": len(value), "sample": value[:3]}
                return summary
        return data
    return {"raw": str(data)[:2000]}


def _json_safe(value):
    """Make preview payloads safe for Celery JSON result serializer."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _resolve_smart_metering_authentication_token(explicit_token=None):
    if explicit_token:
        return explicit_token
    try:
        config = ConfigProject.objects.get(token=SMART_METERING_AUTH_CONFIG_TOKEN)
        if config.value:
            return config.value
    except ConfigProject.DoesNotExist:
        pass
    return getattr(settings, "SMART_METERING_API_TOKEN", "") or ""


def _resolve_smart_metering_exploitation_id():
    """
    Optional ConfigProject `smart_metering_explotation_id`.

    Not sent on massive readings until further notice. Pass
    ``include_exploitation=True`` to ``_request_params`` to turn the filter back on.
    Empty/missing → do not send `exploitation`.
    """
    try:
        config = ConfigProject.objects.get(token=SMART_METERING_EXPLOITATION_CONFIG_TOKEN)
    except ConfigProject.DoesNotExist:
        return None
    value = (config.value or "").strip()
    return value or None


class SmartMeteringClient:
    MASSIVE_READINGS_ENDPOINT = "/massive-readings-by-date/"
    SINGLE_READINGS_ENDPOINT = "/meter-readings-by-date/"

    def __init__(self, base_url=None, token=None, timeout=None, margin=None, auth_param=None):
        self.base_url = (base_url or getattr(settings, "SMART_METERING_API_URL", "") or "").rstrip("/")
        self._explicit_token = token
        self.timeout = timeout or getattr(settings, "SMART_METERING_API_TIMEOUT", 30)
        self.margin = margin if margin is not None else getattr(settings, "SMART_METERING_API_MARGIN", 5)
        self.auth_param = auth_param or getattr(settings, "SMART_METERING_API_AUTH_PARAM", "Authorization")

    @property
    def authentication_token(self):
        return _resolve_smart_metering_authentication_token(self._explicit_token)

    def _headers(self):
        token = self.authentication_token
        if not token:
            raise SmartMeteringApiError(
                f"Smart metering authentication is not configured "
                f"(ConfigProject token: {SMART_METERING_AUTH_CONFIG_TOKEN})"
            )
        return {
            "Accept": "application/json",
            self.auth_param: token,
        }

    def _request_params(self, reading_date, meter_code=None, *, include_exploitation=False):
        date_str = reading_date.isoformat() if hasattr(reading_date, "isoformat") else str(reading_date)
        params = {"date": date_str, "margin": self.margin}
        if include_exploitation:
            exploitation_id = _resolve_smart_metering_exploitation_id()
            if exploitation_id:
                params["exploitation"] = exploitation_id
                logger.info(
                    "Smart metering massive readings: using exploitation=%s",
                    exploitation_id,
                )
            else:
                logger.info(
                    "Smart metering massive readings: smart_metering_explotation_id empty, "
                    "not sending exploitation param"
                )
        if meter_code:
            params["meter"] = meter_code
        return params

    @staticmethod
    def _redact_headers(headers, auth_param):
        redacted = dict(headers)
        if auth_param in redacted:
            redacted[auth_param] = "***"
        return redacted

    def _log(self, *, method, endpoint, request_payload, response_payload=None, status_code=None, success=False, error_message=""):
        IntegrationRequestLog.objects.create(
            provider=PROVIDER,
            direction=IntegrationRequestLog.DIRECTION_OUTBOUND,
            method=method,
            endpoint=endpoint,
            request_payload=request_payload,
            response_payload=response_payload,
            status_code=status_code,
            success=success,
            error_message=error_message,
        )

    def _get(self, endpoint, params, *, log=True, timeout=None, headers=None):
        if not self.base_url:
            raise SmartMeteringApiError("SMART_METERING_API_URL is not configured")

        url = f"{self.base_url}{endpoint}"
        request_headers = headers or self._headers()
        log_payload = {
            "params": params,
            "headers": self._redact_headers(request_headers, self.auth_param),
        }
        request_timeout = timeout if timeout is not None else self.timeout
        try:
            response = requests.get(
                url,
                params=params,
                headers=request_headers,
                timeout=request_timeout,
                verify=True,
            )
        except requests.RequestException as exc:
            msg = f"Error connecting to smart metering API: {exc}"
            if log:
                self._log(method="GET", endpoint=endpoint, request_payload=log_payload, success=False, error_message=msg)
            raise SmartMeteringApiError(msg) from exc

        if not response.ok:
            msg = f"Smart metering API error {response.status_code}: {response.text}"
            if log:
                self._log(
                    method="GET",
                    endpoint=endpoint,
                    request_payload=log_payload,
                    status_code=response.status_code,
                    success=False,
                    error_message=msg,
                )
            raise SmartMeteringApiError(msg)

        try:
            data = response.json()
        except ValueError as exc:
            msg = "Smart metering API response is not valid JSON"
            if log:
                self._log(
                    method="GET",
                    endpoint=endpoint,
                    request_payload=log_payload,
                    status_code=response.status_code,
                    success=False,
                    error_message=msg,
                )
            raise SmartMeteringApiError(msg) from exc

        if log:
            self._log(
                method="GET",
                endpoint=endpoint,
                request_payload=log_payload,
                response_payload=_response_payload_for_log(data),
                status_code=response.status_code,
                success=True,
            )
        return data

    def fetch_readings(self, reading_date):
        # Exploitation filter paused: massive readings go out with date + margin only.
        return self._get(
            self.MASSIVE_READINGS_ENDPOINT,
            self._request_params(reading_date),
        )

    def fetch_meter_reading(self, reading_date, meter_code):
        """Fetch the smart metering reading for a single meter on a given date."""
        return self._get(
            self.SINGLE_READINGS_ENDPOINT,
            self._request_params(reading_date, meter_code=meter_code),
        )


def _parse_reading_date(value):
    if value is None:
        return None
    if hasattr(value, "year") and not isinstance(value, str):
        if hasattr(value, "hour"):
            return value.date()
        return value
    if isinstance(value, str):
        value = value.strip()
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            pass
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value[:19], fmt).date()
            except ValueError:
                continue
    return None


def _extract_api_rows(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("results", "readings", "data"):
            value = payload.get(key)
            if value is None:
                continue
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                return [value]
        if _meter_code_from_api_row(payload):
            return [payload]
    return []


def _meter_code_from_api_row(row):
    if not isinstance(row, dict):
        return None
    code = (
        row.get("meter")
        or row.get("code")
        or row.get("meter_code")
        or row.get("meterCode")
        or row.get("serial")
    )
    if not code:
        return None
    return str(code).strip().replace(" ", "")


def _normalize_meter_code_for_match(code):
    if code is None:
        return ""
    return str(code).strip().replace(" ", "")


def _api_meter_code_candidates(api_code):
    """
    Build match candidates from an API meter code.

    Exact code always included. Prefijo/sufijo de 1 carácter solo se quitan
    si són lletres (A-Z), mai dígits, per evitar falsos positius numèrics.
    """
    code = _normalize_meter_code_for_match(api_code)
    if not code:
        return []
    candidates = [code]
    # Strip letter edges only: "A12345" → "12345", never "123456" → "23456"
    if len(code) > 1 and code[0].isalpha():
        candidates.append(code[1:])
    if len(code) > 1 and code[-1].isalpha():
        candidates.append(code[:-1])
    if len(code) > 2 and code[0].isalpha() and code[-1].isalpha():
        candidates.append(code[1:-1])
    seen = set()
    unique_candidates = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique_candidates.append(candidate)
    return unique_candidates


# Contains-match needs a minimum length; short codes like "12" / "20" false-positive
# against almost every meter in the exploitation and inflate the preview.
SMART_METERING_MIN_CONTAINS_LEN = 5


def _db_code_has_only_letter_affixes(db_code, candidate):
    """
    True if candidate appears in db_code and any extra prefix/suffix are letters only.

    "XABC12345" ⊃ "ABC12345" → True (prefix letter)
    "991234599" ⊃ "12345" → False (digit affixes)
    """
    idx = db_code.find(candidate)
    if idx < 0:
        return False
    prefix = db_code[:idx]
    suffix = db_code[idx + len(candidate) :]
    return (not prefix or prefix.isalpha()) and (not suffix or suffix.isalpha())


def _meter_codes_match_for_smart_metering(db_meter_code, api_meter_code):
    """
    Match API meter identifiers against DB meter codes using contains,
    aligned with import_meter_change_smart_metering / update_meter_remote_reading_smart_metering.

    Exact match always wins. Contains only applies when the API candidate is long
    enough and the leftover DB prefix/suffix are letters (not digits).
    """
    db_code = _normalize_meter_code_for_match(db_meter_code)
    if not db_code:
        return False
    for candidate in _api_meter_code_candidates(api_meter_code):
        if candidate == db_code:
            return True
        if len(candidate) < SMART_METERING_MIN_CONTAINS_LEN:
            continue
        if _db_code_has_only_letter_affixes(db_code, candidate):
            return True
    return False


def _find_api_row_for_meter_code(api_by_code, meter_code):
    db_code = _normalize_meter_code_for_match(meter_code)
    if not db_code or not api_by_code:
        return None
    if db_code in api_by_code:
        return api_by_code[db_code]
    # Prefer the longest matching API code to avoid short false positives.
    best_row = None
    best_len = -1
    for api_code, row in api_by_code.items():
        if not _meter_codes_match_for_smart_metering(db_code, api_code):
            continue
        api_len = len(_normalize_meter_code_for_match(api_code))
        if api_len > best_len:
            best_row = row
            best_len = api_len
    return best_row


def _api_code_matches_any_batch_meter(api_code, batch_meter_codes):
    return any(
        _meter_codes_match_for_smart_metering(db_code, api_code)
        for db_code in batch_meter_codes
    )


def _filter_api_rows_for_batch(api_by_code, batch_meter_codes):
    """Keep only API rows that match at least one meter in the reading batch."""
    if not api_by_code or not batch_meter_codes:
        return {}
    return {
        code: row
        for code, row in api_by_code.items()
        if _api_code_matches_any_batch_meter(code, batch_meter_codes)
    }


def _primary_contract_for_smart_metering(contracts, active_contract_token):
    """
    One contract per supply point for smart-metering preview/assign.

    Prefer the active contract; fall back to the first prefetched candidate
    (e.g. recently terminated still valid for the reading date).
    """
    contracts = list(contracts or [])
    if not contracts:
        return None
    for contract in contracts:
        status_token = getattr(getattr(contract, "status", None), "token", None)
        if status_token == active_contract_token and getattr(contract, "is_active", True):
            return contract
    for contract in contracts:
        status_token = getattr(getattr(contract, "status", None), "token", None)
        if status_token == active_contract_token:
            return contract
    return contracts[0]


def _count_api_readings_for_batch(payload, batch_codes):
    return sum(
        1
        for row in _extract_api_rows(payload)
        if (code := _meter_code_from_api_row(row))
        and _api_code_matches_any_batch_meter(code, batch_codes)
    )


def _normalize_api_rows(payload):
    """
    Normalizes smart metering API payloads.

    Expected item shape:
        { "meter": "03262620", "reading": 1170, "timestamp": "2026-06-02" }
    """
    normalized = {}
    for row in _extract_api_rows(payload):
        code = _meter_code_from_api_row(row)
        if not code:
            continue
        reading_raw = row.get("reading") if row.get("reading") is not None else row.get("reading_value")
        timestamp = row.get("timestamp") or row.get("reading_date") or row.get("date")
        try:
            reading_value = Decimal(str(reading_raw)) if reading_raw is not None else None
        except (InvalidOperation, TypeError, ValueError):
            reading_value = None
        normalized[code] = {
            "code": code,
            "reading_value": reading_value,
            "timestamp": timestamp,
            "reading_date": _parse_reading_date(timestamp),
        }
    return normalized


def _active_contract_filter_q(
    active_contract_token,
    terminated_contract_token,
    contract_termination_completed_token,
    ref_date,
):
    return Q(status__token=active_contract_token, is_active=True) | (
        Q(status__token=terminated_contract_token)
        & Q(contractterminationrequest__status__token=contract_termination_completed_token)
        & (
            Q(contractterminationrequest__approved_at__date__gte=ref_date)
            | Q(
                contractterminationrequest__approved_at__isnull=True,
                contractterminationrequest__created_at__date__gte=ref_date,
            )
        )
    )


def _active_contract_qs(
    supply_point,
    active_contract_token,
    terminated_contract_token,
    contract_termination_completed_token,
    ref_date,
):
    return supply_point.contracts.filter(
        _active_contract_filter_q(
            active_contract_token,
            terminated_contract_token,
            contract_termination_completed_token,
            ref_date,
        )
    ).distinct()


def _active_contracts_prefetch(
    active_contract_token,
    terminated_contract_token,
    contract_termination_completed_token,
    ref_date,
):
    """Prefetch only contracts that are active (or recently terminated) for the given date."""
    return Prefetch(
        "contracts",
        queryset=Contract.objects.filter(
            _active_contract_filter_q(
                active_contract_token,
                terminated_contract_token,
                contract_termination_completed_token,
                ref_date,
            )
        )
        .select_related("holder", "status")
        .distinct(),
        to_attr="active_contracts_for_preview",
    )


def _telecontrol_supply_point_base_qs():
    return SupplyPoint.objects.select_related(
        "meter",
        "meter__status",
        "address",
        "address__street",
        "address__street_number",
        "status",
    )


def _is_smart_metering_meter(meter):
    return bool(
        meter
        and meter.has_remote_reading
        and meter.remote_reading_type == "SMART_METERING"
    )


SMART_METERING_SCOPE_KEYS = ("route_ids", "route_zone_ids", "batch_ids")
SMART_METERING_METER_Q = Q(
    meter__has_remote_reading=True,
    meter__remote_reading_type="SMART_METERING",
)


def normalize_smart_metering_scope(scope):
    """
    Keep only the known keys with integer ids. Returns None when nothing is
    selected, which means "every Smart Metering meter".

    Invalid ids raise ValueError instead of being dropped: dropping them could
    turn the scope into None and load every meter.
    """
    if not isinstance(scope, dict):
        return None
    normalized = {}
    for key in SMART_METERING_SCOPE_KEYS:
        values = scope.get(key)
        if values is None:
            continue
        if not isinstance(values, (list, tuple)):
            values = [values]
        tokens = [str(value).strip() for value in values]
        if any(not token.isascii() or not token.isdigit() or int(token) <= 0 for token in tokens):
            raise ValueError(f"Invalid ids for '{key}'")
        ids = sorted({int(token) for token in tokens})
        if ids:
            normalized[key] = ids
    return normalized or None


def _smart_metering_scope_q(scope):
    """
    Supply points of the selected routes, zones or reading batches (union).

    A batch covers its routes and its fix meters, like the batch setup, but only
    if it includes telecontrol meters (a manuals-only batch has no Smart Metering).
    """
    scope = normalize_smart_metering_scope(scope)
    if not scope:
        return None
    scope_q = Q(pk__in=[])
    if scope.get("route_ids"):
        scope_q |= Q(property__route_position__route_id__in=scope["route_ids"])
    if scope.get("route_zone_ids"):
        scope_q |= Q(property__route_position__route__route_zone_id__in=scope["route_zone_ids"])
    if scope.get("batch_ids"):
        batch_ids = list(
            ReadingBatch.objects.filter(
                id__in=scope["batch_ids"], include_telecontrol=True
            ).values_list("id", flat=True)
        )
        scope_q |= Q(property__route_position__route__reading_batches__in=batch_ids)
        scope_q |= Q(meter__reading_batches__in=batch_ids)
    return scope_q


def smart_metering_scope_supply_point_ids(scope):
    """Ids of the Smart Metering supply points covered by ``scope`` (None = all)."""
    queryset = SupplyPoint.objects.filter(SMART_METERING_METER_Q)
    scope_q = _smart_metering_scope_q(scope)
    if scope_q is not None:
        queryset = queryset.filter(scope_q)
    return set(queryset.values_list("id", flat=True).distinct())


def smart_metering_document_supply_point_ids(reading_document):
    """
    Supply points of a Smart Metering document: those of its scope plus those of
    the readings it already holds (a supply point may have changed route since).
    """
    return smart_metering_scope_supply_point_ids(reading_document.smart_metering_scope) | set(
        reading_document.readings.filter(supply_point__isnull=False).values_list("supply_point_id", flat=True)
    )


def _label(obj):
    return " - ".join(str(value) for value in (obj.token, obj.name) if value) or str(obj.id)


def smart_metering_scope_options():
    """Routes, zones and open reading batches that have Smart Metering meters."""
    route_sm_q = Q(
        positions__properties__supply_points__meter__has_remote_reading=True,
        positions__properties__supply_points__meter__remote_reading_type="SMART_METERING",
    )
    routes = Route.objects.filter(route_sm_q, is_active=True).distinct().order_by("position", "token", "id")
    zones = (
        RouteZone.objects.filter(
            is_active=True,
            routes__is_active=True,
            routes__positions__properties__supply_points__meter__has_remote_reading=True,
            routes__positions__properties__supply_points__meter__remote_reading_type="SMART_METERING",
        )
        .distinct()
        .order_by("position", "name", "id")
    )
    batches = (
        ReadingBatch.objects.filter(
            is_active=True,
            is_processed=False,
            is_excluded=False,
            include_telecontrol=True,
        )
        .filter(
            Q(
                routes__positions__properties__supply_points__meter__has_remote_reading=True,
                routes__positions__properties__supply_points__meter__remote_reading_type="SMART_METERING",
            )
            | Q(fix_meters__has_remote_reading=True, fix_meters__remote_reading_type="SMART_METERING")
        )
        .distinct()
        .order_by("-created_at")
    )
    return {
        "routes": [{"id": route.id, "label": _label(route)} for route in routes],
        "route_zones": [{"id": zone.id, "label": _label(zone)} for zone in zones],
        "batches": [{"id": batch.id, "label": _label(batch)} for batch in batches],
    }


def smart_metering_scope_labels(scope):
    """Readable names of the selected routes, zones and batches (for the document)."""
    scope = normalize_smart_metering_scope(scope)
    if not scope:
        return None
    return {
        "routes": [_label(obj) for obj in Route.objects.filter(id__in=scope.get("route_ids", []))],
        "route_zones": [_label(obj) for obj in RouteZone.objects.filter(id__in=scope.get("route_zone_ids", []))],
        "batches": [_label(obj) for obj in ReadingBatch.objects.filter(id__in=scope.get("batch_ids", []))],
    }


def _collect_telecontrol_targets(reading_date, scope=None):
    """
    Supply points with a Smart Metering meter (``remote_reading_type=SMART_METERING``).

    The load is not tied to a reading batch: it covers the Smart Metering meters
    of the selected routes, zones or batches (all of them if ``scope`` is empty)
    and the batch picks the resulting reading document afterwards.
    """
    active_contract_token = ConfigProject.objects.get(token="contract_active_token").value
    terminated_contract_token = ConfigProject.objects.get(token="contract_terminated_status").value
    contract_termination_completed_token = ConfigProject.objects.get(
        token="contract_termination_completed_token"
    ).value
    token_meter_status_no_meter = ConfigProject.objects.get(token="token_meter_status_no_meter").value
    smart_metering_q = SMART_METERING_METER_Q
    scope_q = _smart_metering_scope_q(scope)
    if scope_q is not None:
        smart_metering_q &= scope_q
    prefetch_args = (
        active_contract_token,
        terminated_contract_token,
        contract_termination_completed_token,
        reading_date,
    )

    targets = []
    seen = set()

    supply_points = (
        _telecontrol_supply_point_base_qs()
        .filter(smart_metering_q)
        .prefetch_related(_active_contracts_prefetch(*prefetch_args))
        .distinct()
        .order_by("id")
    )
    for sp in supply_points:
        meter = sp.meter
        if not _is_smart_metering_meter(meter):
            continue
        if meter.status and meter.status.token == token_meter_status_no_meter:
            continue
        key = (sp.id, meter.id)
        if key in seen:
            continue
        seen.add(key)
        targets.append(sp)

    return targets


def _previous_reading(supply_point, meter, contract, reading_date, exclude_reading=None):
    queryset = Reading.objects.filter(
        supply_point=supply_point,
        meter=meter,
        contract=contract,
        reading_date__lt=reading_date,
        is_control=False,
        is_initial=False,
    )
    if exclude_reading:
        queryset = queryset.exclude(id=exclude_reading.id)
    return queryset.order_by("-reading_date", "-reading_value").first()


def _bulk_previous_readings_by_key(keys, before_date):
    """
    Load previous readings for many (supply_point, meter, contract) keys in one query.

    Returns dict[(sp_id, meter_id, contract_id)] -> list[Reading] ordered by
    reading_date desc, reading_value desc. Caller picks the first whose
    reading_date is strictly before the row's effective date.
    """
    if not keys or not before_date:
        return {}

    key_set = set(keys)
    sp_ids = {sp_id for sp_id, _, _ in key_set}
    meter_ids = {meter_id for _, meter_id, _ in key_set}
    contract_ids = {contract_id for _, _, contract_id in key_set}

    readings = (
        Reading.objects.filter(
            supply_point_id__in=sp_ids,
            meter_id__in=meter_ids,
            contract_id__in=contract_ids,
            reading_date__lt=before_date,
            is_control=False,
            is_initial=False,
        )
        .order_by(
            "supply_point_id",
            "meter_id",
            "contract_id",
            "-reading_date",
            "-reading_value",
        )
        .only(
            "id",
            "supply_point_id",
            "meter_id",
            "contract_id",
            "reading_value",
            "reading_date",
        )
    )

    by_key = {}
    for reading in readings:
        key = (reading.supply_point_id, reading.meter_id, reading.contract_id)
        if key not in key_set:
            continue
        by_key.setdefault(key, []).append(reading)
    return by_key


def _pick_previous_reading(previous_by_key, supply_point_id, meter_id, contract_id, before_date):
    if not before_date:
        return None
    for reading in previous_by_key.get((supply_point_id, meter_id, contract_id), ()):
        if reading.reading_date and reading.reading_date < before_date:
            return reading
    return None


def _calculate_consumption(reading_value, row_reading_date, previous, meter):
    if not previous or previous.reading_value is None:
        consumption_days = (
            (row_reading_date - previous.reading_date).days
            if previous and previous.reading_date
            else 0
        )
        return Decimal("0"), consumption_days

    consumption_days = (row_reading_date - previous.reading_date).days

    if previous.is_close:
        return Decimal("0"), consumption_days

    if reading_value > previous.reading_value:
        return reading_value - previous.reading_value, consumption_days

    if (
        reading_value < previous.reading_value
        and meter
        and previous.meter_id == meter.id
    ):
        overflow_reading = type("OverflowReading", (), {})()
        overflow_reading.reading_value = reading_value
        overflow_reading.meter = meter
        return Decimal(str(check_overflow_value(overflow_reading, previous))), consumption_days

    return reading_value - previous.reading_value, consumption_days


def _calculated_fields(reading_value, previous, row_reading_date, meter=None):
    return _calculate_consumption(reading_value, row_reading_date, previous, meter)


def _find_reading_to_replace(reading_document, supply_point, meter, contract, row_reading_date):
    existing = Reading.objects.filter(
        supply_point=supply_point,
        meter=meter,
        contract=contract,
        reading_date=row_reading_date,
        is_control=False,
        is_initial=False,
    ).first()
    if existing:
        return existing

    # Re-load of the same document (replace): the API may return another date.
    return reading_document.readings.filter(
        supply_point=supply_point,
        meter=meter,
        contract=contract,
        is_control=False,
        is_initial=False,
    ).first()


def _can_replace_reading(reading, reading_document):
    """
    A reading already used by a batch, invoiced, or loaded by another document
    must not be modified by a Smart Metering load (it would leave the other lot
    or document with stale data).
    """
    if reading.batch_id:
        return False
    if reading.document_id and reading.document_id != reading_document.id:
        return False
    return not reading.invoices.exists()


def _mark_reading_as_control(reading):
    if reading.is_control:
        return
    reading.is_control = True
    reading.save(update_fields=["is_control", "updated_at"])


def _link_modified_reading(original_reading, new_reading):
    og_reading = original_reading.original_readings.first() or original_reading
    og_reading.modified_readings.add(new_reading)


def _create_smart_metering_reading(
    reading_document,
    supply_point,
    meter,
    contract,
    row_reading_date,
    reading_value,
    previous,
    calculated_value,
    consumption_days,
):
    return Reading.objects.create(
        token=f"{contract.token}/{meter.code}/SM{row_reading_date.strftime('%y%m%d')}",
        document=reading_document,
        supply_point=supply_point,
        reading_date=row_reading_date,
        reading_value=reading_value,
        meter=meter,
        contract=contract,
        origin=ORIGIN_SMART_METERING,
        is_control=False,
        calculated_value=calculated_value,
        previous_reading=previous,
        consumption_days=consumption_days,
        real_consumption=calculated_value,
        leak_value=0,
    )


def _rechain_future_readings(replaced_reading, new_reading, supply_point, meter, contract):
    if not replaced_reading or not new_reading:
        return

    future_readings = Reading.objects.filter(
        supply_point=supply_point,
        meter=meter,
        contract=contract,
        previous_reading=replaced_reading,
        is_control=False,
        is_initial=False,
    )
    for future in future_readings:
        calculated_value, consumption_days = _calculate_consumption(
            future.reading_value,
            future.reading_date,
            new_reading,
            meter,
        )
        future.previous_reading = new_reading
        future.calculated_value = calculated_value
        future.consumption_days = consumption_days
        future.real_consumption = calculated_value
        future.save(
            update_fields=[
                "previous_reading",
                "calculated_value",
                "consumption_days",
                "real_consumption",
                "updated_at",
            ]
        )


def _save_smart_metering_reading(
    reading_document,
    supply_point,
    meter,
    contract,
    row_reading_date,
    reading_value,
):
    """
    Guarda la lectura de smart metering amb el mateix patró que modify_existing_readings:
    la lectura substituïda passa a control i la nova apunta a l'última lectura activa.
    Retorna None si no es pot desar (lectura existent protegida o anterior a l'última).
    """
    reading_to_replace = _find_reading_to_replace(
        reading_document, supply_point, meter, contract, row_reading_date
    )
    if reading_to_replace and not _can_replace_reading(reading_to_replace, reading_document):
        return None
    previous = _previous_reading(
        supply_point,
        meter,
        contract,
        row_reading_date,
        exclude_reading=reading_to_replace,
    )
    calculated_value, consumption_days = _calculated_fields(
        reading_value, previous, row_reading_date, meter
    )

    if reading_to_replace:
        unchanged = (
            reading_to_replace.reading_value == reading_value
            and reading_to_replace.reading_date == row_reading_date
        )
        if unchanged:
            reading_to_replace.previous_reading = previous
            reading_to_replace.document = reading_document
            reading_to_replace.origin = ORIGIN_SMART_METERING
            reading_to_replace.calculated_value = calculated_value
            reading_to_replace.consumption_days = consumption_days
            reading_to_replace.real_consumption = calculated_value
            reading_to_replace.save(
                update_fields=[
                    "previous_reading",
                    "document",
                    "origin",
                    "calculated_value",
                    "consumption_days",
                    "real_consumption",
                    "updated_at",
                ]
            )
            return reading_to_replace

        _mark_reading_as_control(reading_to_replace)
        new_reading = _create_smart_metering_reading(
            reading_document,
            supply_point,
            meter,
            contract,
            row_reading_date,
            reading_value,
            previous,
            calculated_value,
            consumption_days,
        )
        _link_modified_reading(reading_to_replace, new_reading)
        _rechain_future_readings(
            reading_to_replace, new_reading, supply_point, meter, contract
        )
        return new_reading

    try:
        allow_by_period = check_billing_period(
            row_reading_date, supply_point, meter, contract, previous
        )
    except AttributeError:
        # Supply point without route: the load is no longer limited to batch routes.
        allow_by_period = True
    if allow_by_period or not previous:
        return _create_smart_metering_reading(
            reading_document,
            supply_point,
            meter,
            contract,
            row_reading_date,
            reading_value,
            previous,
            calculated_value,
            consumption_days,
        )

    if previous.reading_date and previous.reading_date > row_reading_date:
        return None

    return _create_smart_metering_reading(
        reading_document,
        supply_point,
        meter,
        contract,
        row_reading_date,
        reading_value,
        previous,
        calculated_value,
        consumption_days,
    )


def _contract_holder_name(contract):
    holder = contract.holder
    if not holder:
        return ""
    return f"{holder.name or ''} {holder.surname or ''}".strip()


def _build_display_row(supply_point, contract, meter, api_row, fallback_date, previous=None):
    reading_date = (api_row or {}).get("reading_date") or fallback_date
    reading_value = (api_row or {}).get("reading_value")
    timestamp = (api_row or {}).get("timestamp")
    address_without_city = (
        get_address_complete_without_city(supply_point.address).strip()
        if supply_point.address
        else ""
    )
    holder_name = _contract_holder_name(contract)

    return {
        "id": supply_point.id,
        "contract_id": contract.id,
        "matched": api_row is not None and reading_value is not None,
        "holder": holder_name,
        "address_complete": address_without_city,
        "last_previous_reading_value": (
            float(previous.reading_value)
            if previous and previous.reading_value is not None
            else None
        ),
        "reading_value": float(reading_value) if reading_value is not None else None,
        "reading_date": reading_date.isoformat() if reading_date else None,
        "timestamp": timestamp,
        "meter_code": meter.code,
        "contracts": [
            {
                "token": contract.token,
                "holder_full_name": holder_name,
                "holder": holder_name,
            }
        ],
    }


def _parse_request_date(reading_date_str):
    if not reading_date_str:
        raise ValueError("reading_date is required")
    if isinstance(reading_date_str, str):
        return datetime.strptime(reading_date_str, "%Y-%m-%d").date()
    return reading_date_str


def _coerce_client_preview(preview, reading_date_str, scope=None):
    if not isinstance(preview, dict):
        raise ValueError("Invalid preview payload")
    readings = preview.get("readings")
    if not isinstance(readings, list) or not all(isinstance(row, dict) for row in readings):
        raise ValueError("Invalid preview readings")
    expected_date = _parse_request_date(reading_date_str)
    preview_date = preview.get("reading_date")
    if preview_date:
        parsed = _parse_request_date(preview_date) if isinstance(preview_date, str) else preview_date
        if parsed != expected_date:
            raise ValueError("Preview reading_date does not match request")
    if normalize_smart_metering_scope(preview.get("scope")) != normalize_smart_metering_scope(scope):
        raise ValueError("Preview scope does not match request")
    # The rows come from the client and the routes may have changed since the
    # preview: reject it (instead of skipping rows) so the user previews again.
    scope_supply_point_ids = smart_metering_scope_supply_point_ids(scope)
    if any(row.get("id") not in scope_supply_point_ids for row in readings):
        raise SmartMeteringPreviewOutdated("Preview rows do not match the selected scope")
    return preview


def build_smart_metering_preview(reading_date_str, api_timeout=None, progress_callback=None, scope=None):
    def _progress(current, total, description=""):
        if progress_callback:
            progress_callback(current, total, description)

    reading_date = _parse_request_date(reading_date_str)
    _progress(0, 100, "targets_loading")

    supply_points = _collect_telecontrol_targets(reading_date, scope)
    batch_codes = {
        _normalize_meter_code_for_match(sp.meter.code)
        for sp in supply_points
        if sp.meter and sp.meter.code
    }
    active_contract_token = ConfigProject.objects.get(token="contract_active_token").value
    _progress(5, 100, "targets_loaded")

    client = SmartMeteringClient(timeout=api_timeout) if api_timeout else SmartMeteringClient()
    # Fetch all readings for the date, then keep only meters that belong to this batch.
    api_payload = client.fetch_readings(reading_date)
    api_by_code = _filter_api_rows_for_batch(_normalize_api_rows(api_payload), batch_codes)
    _progress(40, 100, "api_done")

    # First pass: one slot per telecontrol supply point (primary contract only).
    # Creating one row per active+terminated contract was doubling the preview
    # (~4000 rows for ~2000 meters) and looking like "all meters", not telecontrol.
    slots = []
    matched_codes = set()
    max_effective_date = reading_date

    for supply_point in supply_points:
        meter = supply_point.meter
        if not meter or not meter.has_remote_reading:
            continue
        if meter.remote_reading_type != "SMART_METERING":
            continue
        contract = _primary_contract_for_smart_metering(
            getattr(supply_point, "active_contracts_for_preview", None),
            active_contract_token,
        )
        if not contract:
            continue
        api_row = _find_api_row_for_meter_code(api_by_code, meter.code)
        if api_row:
            matched_codes.add(_normalize_meter_code_for_match(meter.code))

        effective_date = (api_row or {}).get("reading_date") or reading_date
        if effective_date and effective_date > max_effective_date:
            max_effective_date = effective_date
        slots.append((supply_point, contract, meter, api_row, effective_date))

    _progress(70, 100, "slots_ready")
    previous_by_key = _bulk_previous_readings_by_key(
        [(sp.id, meter.id, contract.id) for sp, contract, meter, _, _ in slots],
        max_effective_date,
    )
    _progress(85, 100, "previous_loaded")

    display_rows = []
    for supply_point, contract, meter, api_row, effective_date in slots:
        previous = _pick_previous_reading(
            previous_by_key,
            supply_point.id,
            meter.id,
            contract.id,
            effective_date,
        )
        display_rows.append(
            _build_display_row(
                supply_point,
                contract,
                meter,
                api_row,
                reading_date,
                previous=previous,
            )
        )

    missing_in_api = len([r for r in display_rows if not r.get("matched")])
    matched_count = len([r for r in display_rows if r.get("matched")])
    matched_supply_points = len({r["id"] for r in display_rows if r.get("matched")})
    total_batch_supply_points = len(supply_points)
    api_readings_in_batch = _count_api_readings_for_batch(api_payload, batch_codes)
    discarded_readings = max(0, api_readings_in_batch - total_batch_supply_points)

    counters = {
        "assigned_readings": matched_count,
        "missing_readings": missing_in_api,
        "discarded_readings": discarded_readings,
        "readings_with_reader_alerts": 0,
        "readings_with_remote_alerts": 0,
        "readings_without_reading_value": len(
            [r for r in display_rows if r.get("matched") and r.get("reading_value") is None]
        ),
        "readings_remote_reading": matched_supply_points,
        "readings_inactive_supplypoints": 0,
        "total_telecontrol_in_batch": len(slots),
        "matched_meters": len(matched_codes),
    }

    _progress(100, 100, "done")
    return {
        "readings": display_rows,
        "counters": counters,
        # Do not ship leftover meters from outside the batch to the client.
        "extra_in_api": [],
        "reading_date": reading_date.isoformat(),
        "origin": ORIGIN_SMART_METERING,
        "scope": normalize_smart_metering_scope(scope),
    }


def fetch_smart_metering_meter_reading(meter_code=None, reading_date_str=None, margin=None, meter_id=None):
    """
    Fetch the smart metering reading for a single meter on a given date.

    Either `meter_code` or `meter_id` must be provided. When only `meter_id` is
    given the meter code is resolved from the database. If no date is provided
    the current date is used by default.
    """
    if not meter_code and meter_id:
        from service.models import Meter

        meter = Meter.objects.filter(id=meter_id).first()
        if not meter:
            raise ValueError("Meter not found")
        meter_code = meter.code

    if not meter_code:
        raise ValueError("meter or meter_id is required")

    reading_date = (
        _parse_request_date(reading_date_str) if reading_date_str else timezone.localdate()
    )

    client = SmartMeteringClient(margin=margin)
    api_payload = client.fetch_meter_reading(reading_date, meter_code)
    api_by_code = _normalize_api_rows(api_payload)
    api_row = _find_api_row_for_meter_code(api_by_code, meter_code)

    reading_value = api_row.get("reading_value") if api_row else None
    row_reading_date = api_row.get("reading_date") if api_row else None

    return {
        "meter": meter_code,
        "date": reading_date.isoformat(),
        "found": api_row is not None and reading_value is not None,
        "reading_value": float(reading_value) if reading_value is not None else None,
        "reading_date": row_reading_date.isoformat() if row_reading_date else None,
        "timestamp": api_row.get("timestamp") if api_row else None,
        "origin": ORIGIN_SMART_METERING,
    }


def smart_metering_config_token_value():
    """ConfigProject value for the Smart Metering token, stripped. Empty if missing."""
    try:
        config = ConfigProject.objects.get(token=SMART_METERING_AUTH_CONFIG_TOKEN)
    except ConfigProject.DoesNotExist:
        return ""
    return (config.value or "").strip()


def smart_metering_is_enabled():
    """True only when the Smart Metering ConfigProject token has a written value."""
    return bool(smart_metering_config_token_value())


def _inbound_contracts_path():
    """Path Smart Metering calls to read contracts. Includes /api when that prefix is on."""
    from decouple import config as env_config

    raw = env_config("API_URL_PREFIX", default="False")
    prefix = "/api" if str(raw) == "True" else ""
    return f"{prefix}{SMART_METERING_INBOUND_CONTRACTS_PATH}"


def _truncate_probe_detail(value):
    text = str(value or "").strip()
    if len(text) <= SMART_METERING_PROBE_DETAIL_LIMIT:
        return text
    return text[:SMART_METERING_PROBE_DETAIL_LIMIT] + "…"


def get_smart_metering_settings():
    """
    Connection data for the settings screen.

    The token is the ConfigProject value (not the env fallback). The URL comes
    from SMART_METERING_API_URL.
    """
    token = smart_metering_config_token_value()
    api_url = (getattr(settings, "SMART_METERING_API_URL", "") or "").rstrip("/")
    return {
        "enabled": bool(token),
        "api_url": api_url,
        "authentication_token": token,
        "auth_param": getattr(settings, "SMART_METERING_API_AUTH_PARAM", "Authorization"),
        "timeout": getattr(settings, "SMART_METERING_API_TIMEOUT", 30),
        "margin": getattr(settings, "SMART_METERING_API_MARGIN", 5),
        "inbound_endpoint": _inbound_contracts_path(),
        "massive_readings_endpoint": SmartMeteringClient.MASSIVE_READINGS_ENDPOINT,
        "single_readings_endpoint": SmartMeteringClient.SINGLE_READINGS_ENDPOINT,
    }


_OPENAPI_SPEC_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "integrations"
    / "smartmetering"
    / "openapi.yaml"
)
_OPENAPI_SERVERS_BLOCK = """servers:
  - url: https://customers.example.com
    description: Entorn de producció (substituir pel domini real)
  - url: http://localhost:8000
    description: Entorn local de desenvolupament
"""


def build_smart_metering_openapi(server_url):
    """Public inbound OpenAPI, with this deployment as the server URL."""
    server_url = str(server_url or "").strip().rstrip("/")
    if not server_url or any(char in server_url for char in "\n\r"):
        raise ValueError("server_url_invalid")
    text = _OPENAPI_SPEC_PATH.read_text(encoding="utf-8")
    if _OPENAPI_SERVERS_BLOCK not in text:
        raise ValueError("openapi_template_invalid")
    servers = (
        "servers:\n"
        f"  - url: {server_url}\n"
        "    description: Aquest desplegament\n"
    )
    return text.replace(_OPENAPI_SERVERS_BLOCK, servers, 1)


def build_smart_metering_server_curl(reading_date_str=None, meter_code=None):
    """
    Shell script that calls Smart Metering for one day.

    The token is inside the script so it can be run on the server. Callers must
    not print the result.
    """
    import shlex
    from urllib.parse import urlencode

    if not smart_metering_is_enabled():
        raise ValueError("not_configured")
    connection = get_smart_metering_settings()
    if not connection["api_url"]:
        raise ValueError("url_missing")
    reading_date = _parse_probe_date(reading_date_str) if reading_date_str else timezone.localdate()
    meter = str(meter_code).strip() if meter_code not in (None, "") else ""
    meter = meter or None
    endpoint = (
        SmartMeteringClient.SINGLE_READINGS_ENDPOINT
        if meter
        else SmartMeteringClient.MASSIVE_READINGS_ENDPOINT
    )
    params = {"date": reading_date.isoformat(), "margin": connection["margin"]}
    if meter:
        params["meter"] = meter
    url = f"{connection['api_url']}{endpoint}?{urlencode(params)}"
    header_accept = shlex.quote("Accept: application/json")
    header_auth = shlex.quote(f"{connection['auth_param']}: {connection['authentication_token']}")
    quoted_url = shlex.quote(url)
    timeout = int(SMART_METERING_PREVIEW_API_TIMEOUT)
    return (
        "#!/bin/sh\n"
        "# Prova de lectures Smart Metering. Executar-la al servidor.\n"
        "# No desa lectures al programa.\n"
        "set -eu\n"
        "curl --fail-with-body --silent --show-error "
        f"--max-time {timeout} \\\n"
        f"  --header {header_accept} \\\n"
        f"  --header {header_auth} \\\n"
        f"  {quoted_url}\n"
    )


def _parse_probe_date(reading_date_str):
    if reading_date_str is None or str(reading_date_str).strip() == "":
        raise ValueError("reading_date_required")
    try:
        return datetime.strptime(str(reading_date_str).strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("reading_date_invalid") from exc


def probe_smart_metering_connectivity():
    """
    Ask the Smart Metering host whether it answers.

    Any HTTP status means the host is reachable. 401/403 means the token was rejected.
    This does not load readings.
    """
    client = SmartMeteringClient(timeout=SMART_METERING_CONNECTIVITY_TIMEOUT)
    url = client.base_url
    endpoint = client.SINGLE_READINGS_ENDPOINT
    if not smart_metering_is_enabled():
        return {
            "reachable": False,
            "authenticated": None,
            "status_code": None,
            "elapsed_ms": 0,
            "url": url,
            "code": "not_configured",
            "detail": "",
        }
    if not url:
        return {
            "reachable": False,
            "authenticated": None,
            "status_code": None,
            "elapsed_ms": 0,
            "url": "",
            "code": "url_missing",
            "detail": "SMART_METERING_API_URL is not configured",
        }

    # A fake meter on the single-reading endpoint: the host and the token are
    # checked without downloading the day's massive payload.
    probe_meter = "__connectivity_probe__"
    params = client._request_params(timezone.localdate(), meter_code=probe_meter)
    started = time.perf_counter()
    try:
        response = requests.get(
            f"{url}{endpoint}",
            params=params,
            headers=client._headers(),
            timeout=SMART_METERING_CONNECTIVITY_TIMEOUT,
            verify=True,
            stream=True,
        )
    except requests.RequestException as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        detail = _truncate_probe_detail(f"Error connecting to smart metering API: {exc}")
        client._log(
            method="GET",
            endpoint=endpoint,
            request_payload={"probe": "connectivity", "params": params},
            success=False,
            error_message=detail,
        )
        return {
            "reachable": False,
            "authenticated": None,
            "status_code": None,
            "elapsed_ms": elapsed_ms,
            "url": url,
            "code": "unreachable",
            "detail": detail,
        }

    try:
        status_code = response.status_code
    finally:
        response.close()

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    authenticated = status_code not in (401, 403)
    accepted = authenticated and status_code < 500
    client._log(
        method="GET",
        endpoint=endpoint,
        request_payload={"probe": "connectivity", "params": params},
        status_code=status_code,
        success=accepted,
        error_message="" if accepted else f"HTTP {status_code}",
    )
    code = "ok"
    if not authenticated:
        code = "unauthorized"
    elif status_code >= 500:
        code = "server_error"
    return {
        "reachable": True,
        "authenticated": authenticated,
        "status_code": status_code,
        "elapsed_ms": elapsed_ms,
        "url": url,
        "code": code,
        "detail": "",
    }


def _probe_sample(payload):
    sample = []
    rows = _extract_api_rows(payload)
    for row in rows[:SMART_METERING_PROBE_SAMPLE_LIMIT]:
        if not isinstance(row, dict):
            continue
        reading = row.get("reading") if row.get("reading") is not None else row.get("reading_value")
        sample.append({
            "meter": _meter_code_from_api_row(row),
            "reading": reading,
            "timestamp": row.get("timestamp") or row.get("reading_date") or row.get("date"),
        })
    return rows, sample


def probe_smart_metering_readings(reading_date_str, meter_code=None):
    """
    Fetch readings for one day from Smart Metering and return a short sample.

    Does not create a reading document. With a meter code, calls the single-meter
    endpoint; otherwise the massive readings endpoint (same source as the load).
    """
    reading_date = _parse_probe_date(reading_date_str)
    meter = str(meter_code).strip() if meter_code not in (None, "") else ""
    meter = meter or None
    endpoint = (
        SmartMeteringClient.SINGLE_READINGS_ENDPOINT
        if meter
        else SmartMeteringClient.MASSIVE_READINGS_ENDPOINT
    )
    base = {
        "ok": False,
        "reading_date": reading_date.isoformat(),
        "meter": meter,
        "count": 0,
        "sample": [],
        "sample_limit": SMART_METERING_PROBE_SAMPLE_LIMIT,
        "elapsed_ms": 0,
        "endpoint": endpoint,
        "detail": "",
        "code": "",
    }
    if not smart_metering_is_enabled():
        base["code"] = "not_configured"
        return base

    client = SmartMeteringClient(timeout=SMART_METERING_PREVIEW_API_TIMEOUT)
    started = time.perf_counter()
    try:
        if meter:
            payload = client.fetch_meter_reading(reading_date, meter)
        else:
            payload = client.fetch_readings(reading_date)
    except SmartMeteringApiError:
        logger.exception("Smart metering provider error during readings probe")
        base["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
        base["code"] = "provider_error"
        base["detail"] = "Provider error"
        return base

    rows, sample = _probe_sample(payload)
    base.update({
        "ok": True,
        "count": len(rows),
        "sample": sample,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "code": "ok" if rows else "empty",
    })
    return base


def _row_reading_date(row, fallback_date):
    if row.get("reading_date"):
        return _parse_request_date(row["reading_date"])
    return fallback_date


def _append_reading(readings_to_assign, reading_ids, reading):
    if reading and reading.id not in reading_ids:
        reading_ids.add(reading.id)
        readings_to_assign.append(reading)


SKIP_REASON_NO_API_READING = "no_api_reading"
SKIP_REASON_NOT_SAVED = "existing_reading_protected_or_older"


def find_smart_metering_documents(reading_date, scope=None):
    """
    Smart Metering reading documents of ``reading_date`` whose routes, zones or
    batches (or its readings) share some meter with ``scope``. Only one load per
    date and meter: different routes can be loaded separately for the same date.
    """
    documents = ReadingDocument.objects.filter(
        source=ReadingDocument.SOURCE_SMART_METERING,
        reading_date=reading_date,
    ).order_by("-created_at")
    target_ids = smart_metering_scope_supply_point_ids(scope)
    return [
        document
        for document in documents
        if target_ids & smart_metering_document_supply_point_ids(document)
        or (not target_ids and not normalize_smart_metering_scope(document.smart_metering_scope))
    ]


def smart_metering_document_is_replaceable(reading_document):
    """
    A Smart Metering document can be loaded again only while none of its readings
    has been used: not linked to a batch and no reading in a batch or invoiced.
    """
    if reading_document.batch_id:
        return False
    readings = reading_document.readings.all()
    if readings.filter(batch__isnull=False).exists():
        return False
    return not readings.filter(invoices__isnull=False).exists()


def _build_smart_metering_workbook(readings, not_loaded_rows):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "readings"
    ws.append([
        "meter", "reading_value", "reading_date", "origin",
        "contract", "holder", "address", "previous_reading_value", "consumption",
    ])
    for reading in readings:
        previous = reading.previous_reading
        ws.append([
            reading.meter.code if reading.meter else "",
            float(reading.reading_value) if reading.reading_value is not None else None,
            reading.reading_date.isoformat() if reading.reading_date else "",
            reading.origin or "",
            reading.contract.token if reading.contract else "",
            _contract_holder_name(reading.contract) if reading.contract else "",
            (
                get_address_complete_without_city(reading.supply_point.address).strip()
                if reading.supply_point and reading.supply_point.address
                else ""
            ),
            float(previous.reading_value) if previous and previous.reading_value is not None else None,
            float(reading.calculated_value) if reading.calculated_value is not None else None,
        ])

    ws_missing = wb.create_sheet("not_loaded")
    ws_missing.append(["meter", "contract", "holder", "address", "reading_value", "reading_date", "reason"])
    for row, reason in not_loaded_rows:
        ws_missing.append([
            row.get("meter_code") or "",
            ((row.get("contracts") or [{}])[0]).get("token") or "",
            row.get("holder") or "",
            row.get("address_complete") or "",
            row.get("reading_value"),
            row.get("reading_date") or "",
            reason,
        ])

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def import_smart_metering_readings(reading_document, preview=None):
    """
    Save the Smart Metering readings of ``reading_document.reading_date`` into the
    document (``batch`` stays empty: the reading batch picks the document later,
    like any uploaded readings file) and attach an Excel with the loaded readings.
    """
    reading_date_str = reading_document.reading_date.isoformat()
    if preview is None:
        preview = build_smart_metering_preview(
            reading_date_str, scope=reading_document.smart_metering_scope
        )
    else:
        preview = _coerce_client_preview(
            preview, reading_date_str, reading_document.smart_metering_scope
        )
    fallback_date = reading_document.reading_date
    saved_readings = []
    reading_ids = set()
    set_added_readings = set()
    preview_rows = preview["readings"]
    not_loaded_rows = [
        (row, SKIP_REASON_NO_API_READING) for row in preview_rows if not row.get("matched")
    ]

    matched_rows = [row for row in preview_rows if row.get("matched")]
    supply_points_by_id = {
        sp.id: sp
        for sp in SupplyPoint.objects.filter(
            id__in={row["id"] for row in matched_rows}
        ).select_related("meter")
    }
    contracts_by_id = {
        contract.id: contract
        for contract in Contract.objects.filter(
            id__in={row["contract_id"] for row in matched_rows}
        )
    }

    for row in matched_rows:
        supply_point = supply_points_by_id.get(row["id"])
        if not supply_point:
            continue
        meter = supply_point.meter
        if not meter:
            continue

        contract = contracts_by_id.get(row["contract_id"])
        if not contract:
            continue
        dedupe_key = (contract.token, str(meter.code).strip())
        if dedupe_key in set_added_readings:
            continue
        set_added_readings.add(dedupe_key)

        row_reading_date = _row_reading_date(row, fallback_date)
        reading_value = Decimal(str(row["reading_value"]))

        new_reading = _save_smart_metering_reading(
            reading_document,
            supply_point,
            meter,
            contract,
            row_reading_date,
            reading_value,
        )
        if new_reading:
            _append_reading(saved_readings, reading_ids, new_reading)
        else:
            not_loaded_rows.append((row, SKIP_REASON_NOT_SAVED))

    readings_for_file = (
        Reading.objects.filter(id__in=reading_ids)
        .select_related(
            "meter", "contract__holder", "supply_point__address__street",
            "supply_point__address__street_number", "previous_reading",
        )
        .order_by("meter__code")
    )
    file_bytes = _build_smart_metering_workbook(readings_for_file, not_loaded_rows)
    if reading_document.file:
        reading_document.file.delete(save=False)
    reading_document.file.save(
        f"smart_metering_{reading_document.reading_date.strftime('%Y%m%d')}.xlsx",
        ContentFile(file_bytes),
        save=False,
    )
    reading_document.status = ReadingDocument.STATUS_PROCESSED
    reading_document.processed_at = timezone.now()
    reading_document.save(update_fields=["file", "status", "processed_at", "updated_at"])

    return {
        "document_id": reading_document.id,
        "saved_readings": len(saved_readings),
        "not_saved_readings": len([1 for _, reason in not_loaded_rows if reason == SKIP_REASON_NOT_SAVED]),
        "missing_readings": len([1 for _, reason in not_loaded_rows if reason == SKIP_REASON_NO_API_READING]),
    }
