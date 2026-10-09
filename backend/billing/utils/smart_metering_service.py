
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import requests
from django.conf import settings
from django.db.models import Prefetch, Q
from django.utils import timezone

from billing.models import Reading, ReadingBatch, ReadingBatchStatus
from billing.utils.reading_service import check_billing_period, check_overflow_value
from contract.models import Contract
from coredata.models import ConfigProject
from coredata.utils.address_utils import get_address_complete_without_city
from integrations.models import IntegrationRequestLog
from service.models import SupplyPoint
from billing.utils.reading_filters import PENDING_READING_FILTER

logger = logging.getLogger(__name__)

PROVIDER = "smart_metering"
ORIGIN_SMART_METERING = "SMART METERING"
SMART_METERING_AUTH_CONFIG_TOKEN = "smart_metering_authentication_token"
SMART_METERING_EXPLOITATION_CONFIG_TOKEN = "smart_metering_explotation_id"
# Preview runs in Celery; allow a longer wait for the massive external API.
SMART_METERING_PREVIEW_API_TIMEOUT = 120


class SmartMeteringApiError(Exception):
    pass


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


def _meter_in_reading_batch_scope(reading_batch, meter):
    """
    Same include_telecontrol / include_manual rules as ReadingBatchSetupViewSet
    and assign_readings: a meter on a shared route is NOT in this batch if the
    batch was created with the opposite filter (e.g. manuals-only).
    """
    if not meter:
        return False
    if not reading_batch.include_telecontrol:
        return not meter.has_remote_reading
    if not reading_batch.include_manual:
        return meter.has_remote_reading
    return True


def _is_smart_metering_meter(meter):
    return bool(
        meter
        and meter.has_remote_reading
        and meter.remote_reading_type == "SMART_METERING"
    )


def _collect_batch_telecontrol_targets(reading_batch, reading_date):
    """
    Smart Metering meters that actually belong to this batch.

    Scope = meters on the batch routes (or fix_meters) that pass the batch's
    ``include_telecontrol`` / ``include_manual`` filters, AND have
    ``remote_reading_type=SMART_METERING``.

    Sharing a route with another batch is not enough: a manuals-only batch must
    not surface telecontrol meters that belong to a different lot on the same routes.
    """
    if not reading_batch.include_telecontrol:
        return []

    active_contract_token = ConfigProject.objects.get(token="contract_active_token").value
    terminated_contract_token = ConfigProject.objects.get(token="contract_terminated_status").value
    contract_termination_completed_token = ConfigProject.objects.get(
        token="contract_termination_completed_token"
    ).value
    token_meter_status_no_meter = ConfigProject.objects.get(token="token_meter_status_no_meter").value
    smart_metering_q = Q(
        meter__has_remote_reading=True,
        meter__remote_reading_type="SMART_METERING",
    )
    prefetch_args = (
        active_contract_token,
        terminated_contract_token,
        contract_termination_completed_token,
        reading_date,
    )

    targets = []
    seen = set()

    # Same route → SP query as ReadingBatchSetupViewSet, then Smart Metering only.
    route_sps = (
        _telecontrol_supply_point_base_qs()
        .filter(property__route_position__route__reading_batches=reading_batch)
        .filter(smart_metering_q)
    )
    # Manuals-only is already handled above; telecontrol-only still needs the filter.
    if not reading_batch.include_manual:
        route_sps = route_sps.filter(meter__has_remote_reading=True)
    route_sps = route_sps.prefetch_related(_active_contracts_prefetch(*prefetch_args)).distinct()

    for sp in route_sps:
        meter = sp.meter
        if not _is_smart_metering_meter(meter):
            continue
        if meter.status and meter.status.token == token_meter_status_no_meter:
            continue
        if not _meter_in_reading_batch_scope(reading_batch, meter):
            continue
        key = (sp.id, meter.id)
        if key in seen:
            continue
        seen.add(key)
        targets.append(sp)

    # Explicit fix_meters on the batch (same as setup: always part of the lot when linked).
    fix_sps = (
        _telecontrol_supply_point_base_qs()
        .filter(
            meter__reading_batches=reading_batch,
            meter__has_remote_reading=True,
            meter__remote_reading_type="SMART_METERING",
        )
        .prefetch_related(_active_contracts_prefetch(*prefetch_args))
        .distinct()
    )
    for sp in fix_sps:
        meter = sp.meter
        if not _is_smart_metering_meter(meter):
            continue
        if not _meter_in_reading_batch_scope(reading_batch, meter):
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


def _find_reading_to_replace(reading_batch, supply_point, meter, contract, row_reading_date):
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

    return reading_batch.readings.filter(
        supply_point=supply_point,
        meter=meter,
        contract=contract,
        is_control=False,
        is_initial=False,
    ).first()


def _mark_reading_as_control(reading):
    if reading.is_control:
        return
    reading.is_control = True
    reading.save(update_fields=["is_control", "updated_at"])


def _link_modified_reading(original_reading, new_reading):
    og_reading = original_reading.original_readings.first() or original_reading
    og_reading.modified_readings.add(new_reading)


def _create_smart_metering_reading(
    reading_batch,
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
        batch=reading_batch,
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
    reading_batch,
    supply_point,
    meter,
    contract,
    row_reading_date,
    reading_value,
):
    """
    Guarda la lectura de smart metering amb el mateix patró que modify_existing_readings:
    la lectura substituïda passa a control i la nova apunta a l'última lectura activa.
    """
    reading_to_replace = _find_reading_to_replace(
        reading_batch, supply_point, meter, contract, row_reading_date
    )
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
            reading_to_replace.batch = reading_batch
            reading_to_replace.origin = ORIGIN_SMART_METERING
            reading_to_replace.calculated_value = calculated_value
            reading_to_replace.consumption_days = consumption_days
            reading_to_replace.real_consumption = calculated_value
            reading_to_replace.save(
                update_fields=[
                    "previous_reading",
                    "batch",
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
            reading_batch,
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

    allow_by_period = check_billing_period(
        row_reading_date, supply_point, meter, contract, previous
    )
    if allow_by_period or not previous:
        return _create_smart_metering_reading(
            reading_batch,
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
        reading_batch,
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


def _coerce_client_preview(preview, reading_date_str):
    if not isinstance(preview, dict):
        raise ValueError("Invalid preview payload")
    readings = preview.get("readings")
    if not isinstance(readings, list):
        raise ValueError("Invalid preview readings")
    expected_date = _parse_request_date(reading_date_str)
    preview_date = preview.get("reading_date")
    if preview_date:
        parsed = _parse_request_date(preview_date) if isinstance(preview_date, str) else preview_date
        if parsed != expected_date:
            raise ValueError("Preview reading_date does not match request")
    return preview


def build_smart_metering_preview(reading_batch, reading_date_str, api_timeout=None, progress_callback=None):
    def _progress(current, total, description=""):
        if progress_callback:
            progress_callback(current, total, description)

    reading_date = _parse_request_date(reading_date_str)
    _progress(0, 100, "targets_loading")

    # Smart metering only applies to telecontrol meters included in the batch.
    if not reading_batch.include_telecontrol:
        _progress(100, 100, "done")
        return {
            "readings": [],
            "counters": {
                "assigned_readings": 0,
                "missing_readings": 0,
                "discarded_readings": 0,
                "readings_with_reader_alerts": 0,
                "readings_with_remote_alerts": 0,
                "readings_without_reading_value": 0,
                "readings_remote_reading": 0,
                "readings_inactive_supplypoints": 0,
                "total_telecontrol_in_batch": 0,
                "matched_meters": 0,
            },
            "extra_in_api": [],
            "reading_date": reading_date.isoformat(),
            "origin": ORIGIN_SMART_METERING,
        }

    supply_points = _collect_batch_telecontrol_targets(reading_batch, reading_date)
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


def _row_reading_date(row, fallback_date):
    if row.get("reading_date"):
        return _parse_request_date(row["reading_date"])
    return fallback_date


def _append_reading(readings_to_assign, reading_ids, reading):
    if reading and reading.id not in reading_ids:
        reading_ids.add(reading.id)
        readings_to_assign.append(reading)


def _merge_smart_metering_into_batch(reading_batch, readings_to_assign, reading_ids, replaced_keys):
    """
    Link smart metering readings to the batch without removing any other batch readings.
    """
    if not readings_to_assign:
        return

    attach_ids = [reading.pk for reading in readings_to_assign if reading.batch_id != reading_batch.id]
    if attach_ids:
        Reading.objects.filter(pk__in=attach_ids).update(batch=reading_batch)


def _build_batch_pending_counters(reading_batch):
    """Counters aligned with ReadingBatchSummaryView after readings are persisted."""
    from django.db.models import Count

    active_contract = ConfigProject.objects.get(token="contract_active_token").value
    supply_active_token = ConfigProject.objects.get(token="supply_point_status_activate_token").value
    supply_cut_token = ConfigProject.objects.get(token="supply_point_status_cut_token").value

    non_control_readings = reading_batch.readings.filter(is_control=False)
    pending_filter = PENDING_READING_FILTER
    pending_readings = non_control_readings.filter(pending_filter).distinct()

    sp_query = SupplyPoint.objects.filter(
        property__route_position__route__reading_batches=reading_batch,
    )
    if reading_batch.include_telecontrol and not reading_batch.include_manual:
        sp_query = sp_query.filter(meter__has_remote_reading=True)
    elif reading_batch.include_manual and not reading_batch.include_telecontrol:
        sp_query = sp_query.filter(meter__has_remote_reading=False)

    batch_sp_ids = set(sp_query.values_list("id", flat=True))
    fix_sp_ids = set(SupplyPoint.objects.filter(meter__reading_batches=reading_batch).values_list("id", flat=True))
    batch_sp_ids.update(fix_sp_ids)
    readings_sp_ids = set(non_control_readings.values_list("supply_point_id", flat=True))
    missing_sp_ids = batch_sp_ids - readings_sp_ids
    missing_readings_count = SupplyPoint.objects.filter(
        id__in=missing_sp_ids,
        contracts__status__token=active_contract,
    ).distinct().count()

    if reading_batch.documents.exists():
        num_readings_in_files = reading_batch.documents.aggregate(
            total=Count("readings__id", filter=Q(readings__is_control=False), distinct=True)
        )["total"] or 0
    else:
        num_readings_in_files = 0

    return {
        "assigned_readings": pending_readings.count(),
        "missing_readings": missing_readings_count,
        "discarded_readings": max(0, num_readings_in_files - len(batch_sp_ids)),
        "readings_with_reader_alerts": pending_readings.filter(reader_alert__isnull=False).values("supply_point_id").distinct().count(),
        "readings_with_remote_alerts": pending_readings.filter(remote_alert__isnull=False).values("supply_point_id").distinct().count(),
        "readings_without_reading_value": pending_readings.filter(reading_value__isnull=True).values("supply_point_id").distinct().count(),
        "readings_remote_reading": pending_readings.filter(meter__has_remote_reading=True).values("supply_point_id").distinct().count(),
        "readings_inactive_supplypoints": pending_readings.exclude(
            supply_point__status__token__in=[supply_active_token, supply_cut_token]
        ).values("supply_point_id").distinct().count(),
    }


def assign_smart_metering_readings(reading_batch, reading_date_str, preview=None):
    if preview is None:
        preview = build_smart_metering_preview(reading_batch, reading_date_str)
    else:
        preview = _coerce_client_preview(preview, reading_date_str)
    fallback_date = _parse_request_date(reading_date_str)
    readings_to_assign = []
    reading_ids = set()
    set_added_readings = set()

    matched_rows = [row for row in preview["readings"] if row.get("matched")]
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
            reading_batch,
            supply_point,
            meter,
            contract,
            row_reading_date,
            reading_value,
        )
        if new_reading:
            _append_reading(readings_to_assign, reading_ids, new_reading)

    if readings_to_assign:
        _merge_smart_metering_into_batch(
            reading_batch,
            readings_to_assign,
            reading_ids,
            set_added_readings,
        )

    pending_processing_token = ConfigProject.objects.get(token="reading_batch_pending_processing_token").value
    reading_batch.status = ReadingBatchStatus.objects.get(token=pending_processing_token)
    reading_batch.assign_readings_task_id = None
    reading_batch.save(update_fields=["status", "assign_readings_task_id"])

    return _build_batch_pending_counters(reading_batch)
