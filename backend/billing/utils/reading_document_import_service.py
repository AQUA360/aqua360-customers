from decimal import Decimal

from django.db.models import Q

from billing.models import Reading
from billing.tasks import (
    _parse_reading_document_numeric_value,
    _reading_value_from_liters,
    iter_reading_document_rows,
    parse_reading_document_date,
)
from billing.utils.reading_service import check_billing_period, get_reading_document_target_contract
from contract.models import Contract
from coredata.models import ConfigProject
from service.models import Meter

VALID_PREVIEW_ACTIONS = frozenset({"would_create", "would_update", "not_found", "skip"})
VALID_PREVIEW_REASONS = frozenset({
    "skipped_existing",
    "skipped_no_date",
    "no_supply_points",
    "no_contracts",
})
SEARCH_FIELDS = ("meter_code", "comm_module", "contract_token")


class ReadingDocumentPreviewValidationError(ValueError):
    """Invalid filter/pagination params for reading document preview."""


def build_reading_document_labels(document):
    labels = {
        "meter_label": "meter",
        "observation_label": "observation",
        "reading_value_label": "reading_value",
        "reading_label": "reading",
        "reading_date_label": "reading_date",
        "origin_label": "origin",
        "leak_value_label": "leak_value",
        "is_control_label": "is_control",
        "contract_label": "contract",
        "comm_module_label": "comm_module",
    }
    if document.template:
        for column in document.template.columns.all():
            # mapped_name buit = camp no mapejat. No sobreescriure amb "" perquè
            # csv.DictReader exposa columnes sense capçalera com a clau "" i
            # row.get("") agafa valors spurious (p. ex. "5413" del final de fila).
            mapped = (column.mapped_name or "").strip()
            labels[column.original_name + "_label"] = mapped
    return labels


def _label_is_mapped(labels, label_key):
    return bool(str(labels.get(label_key) or "").strip())


def _row_get_mapped(row, labels, label_key, default=None):
    """Read a CSV cell only if the template maps a non-empty column name."""
    if not _label_is_mapped(labels, label_key):
        return default
    value = row.get(labels[label_key], default)
    if value is None:
        return default
    if isinstance(value, str) and value.strip() == "" and default is not None:
        return default
    return value


def resolve_reading_document_meter(row, labels):
    meter_token = None
    if _label_is_mapped(labels, "meter_label"):
        meter_token = row.get(labels["meter_label"])
    if not meter_token:
        meter_token = row.get("\ufeffmeter", row.get("meter_id", row.get("\ufeffmeter_id")))

    comm_module = _row_get_mapped(row, labels, "comm_module_label")

    meter = None
    if meter_token:
        meter = Meter.objects.filter(code=meter_token).first()
        if not meter:
            meter = Meter.objects.filter(token=meter_token).first()
        if not meter:
            meter = Meter.objects.filter(code=meter_token[:-1]).first()
        if not meter:
            meter = Meter.objects.filter(code=meter_token[1:]).first()
        if not meter:
            meter = Meter.objects.filter(code=meter_token[1:-1]).first()
        if not meter:
            for length in [8, 9, 10]:
                padded_token = meter_token.zfill(length)
                meter = Meter.objects.filter(code=padded_token).first()

    if not meter and comm_module and str(comm_module).strip():
        meter = (
            Meter.objects.filter(comm_module=str(comm_module).strip())
            .exclude(Q(comm_module__isnull=True) | Q(comm_module=""))
            .first()
        )

    if not meter and _label_is_mapped(labels, "contract_label"):
        contract_token = row.get(labels["contract_label"])
        contract = Contract.objects.filter(token=contract_token).first()
        if contract:
            meter = contract.supply_point_default.meter if contract.supply_point_default else None

    return meter, meter_token, comm_module


def _parse_reading_document_row_value(row, labels, template_is_liters):
    raw_reading_value = _row_get_mapped(row, labels, "reading_value_label", "0")
    raw_reading = _row_get_mapped(row, labels, "reading_label", row.get("reading", "0"))
    if template_is_liters:
        reading_value_str = _reading_value_from_liters(raw_reading_value)
        reading_str = _reading_value_from_liters(raw_reading)
    else:
        reading_value_str = _parse_reading_document_numeric_value(raw_reading_value)
        reading_str = _parse_reading_document_numeric_value(raw_reading)
    return max(reading_value_str, reading_str), raw_reading_value


def _get_reading_document_import_config():
    return {
        "active_contract_status_token": ConfigProject.objects.get(token="contract_active_token").value,
        "type_final": ConfigProject.objects.get(token="invoice_type_invoice_token").value,
        "invoice_status_cancelled": ConfigProject.objects.get(token="invoice_status_cancelled_token").value,
        "invoice_status_pending": ConfigProject.objects.get(token="invoice_status_pending_token").value,
    }


def _empty_preview_stats():
    return {
        "rows": 0,
        "skipped_no_date": 0,
        "not_found_meter": 0,
        "no_supply_points": 0,
        "no_contracts": 0,
        "skipped_existing": 0,
        "would_create": 0,
        "would_update": 0,
    }


PREVIEW_SCHEMA_VERSION = 5


def _json_safe_number(value):
    """Coerce DB numerics (Decimal) to JSON-serializable int/float."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, (int, float)):
        return value
    try:
        as_float = float(value)
        if as_float.is_integer():
            return int(as_float)
        return as_float
    except (TypeError, ValueError):
        return value


def _parse_preview_is_control(row, labels):
    raw = _row_get_mapped(row, labels, "is_control_label", "")
    return str(raw).strip().lower() in ["true", "1", "yes", "on"]


def _parse_preview_leak_value(row, labels):
    try:
        return int(float(_row_get_mapped(row, labels, "leak_value_label", 0) or 0))
    except (ValueError, TypeError):
        return 0


def _parse_preview_origin(row, labels):
    origin = _row_get_mapped(row, labels, "origin_label", "TELECONTROL")
    if origin is None:
        origin = "TELECONTROL"
    origin = str(origin).upper()
    if origin.lower() == "estimada":
        return "MANUAL"
    return origin


def _parse_preview_observation(row, labels):
    observation = _row_get_mapped(row, labels, "observation_label", "")
    if observation is None:
        return ""
    return str(observation)


def _build_preview_row_fields(row, labels, *, template_is_liters=False):
    """Effective values that process would use (same defaults as Celery task)."""
    try:
        reading_value, raw_reading_value = _parse_reading_document_row_value(
            row, labels, template_is_liters
        )
    except (ValueError, TypeError):
        reading_value = 0
        raw_reading_value = _row_get_mapped(row, labels, "reading_value_label")

    reading_date_str = _row_get_mapped(
        row, labels, "reading_date_label", row.get("timestamp")
    )
    return {
        "reading_date_raw": reading_date_str,
        "reading_value": reading_value,
        "raw_reading_value": raw_reading_value,
        "origin": _parse_preview_origin(row, labels),
        "is_control": _parse_preview_is_control(row, labels),
        "leak_value": _parse_preview_leak_value(row, labels),
        "observation": _parse_preview_observation(row, labels),
    }


def _preview_row(
    *,
    row_index,
    action,
    fields,
    reason=None,
    meter_code=None,
    comm_module=None,
    contract_token=None,
    supply_point_id=None,
    reading_date=None,
    previous_reading_value=None,
    reading_value=None,
    raw_reading_value=None,
):
    """Full preview row payload shared by all actions."""
    payload = {
        "row_index": row_index,
        "action": action,
        "reason": reason,
        "meter_code": meter_code,
        "comm_module": comm_module,
        "contract_token": contract_token,
        "supply_point_id": supply_point_id,
        "reading_date": reading_date,
        "reading_date_raw": fields.get("reading_date_raw"),
        "reading_value": _json_safe_number(
            reading_value if reading_value is not None else fields.get("reading_value")
        ),
        "raw_reading_value": (
            raw_reading_value if raw_reading_value is not None else fields.get("raw_reading_value")
        ),
        "previous_reading_value": _json_safe_number(previous_reading_value),
        "origin": fields.get("origin"),
        "is_control": fields.get("is_control"),
        "leak_value": _json_safe_number(fields.get("leak_value")),
        "observation": fields.get("observation"),
    }
    return payload


def build_reading_document_preview(document):
    """Build a complete preview (all row entries + full-file stats). No pagination."""
    uploaded_file = document.file
    if not uploaded_file:
        raise ValueError("El document no té fitxer associat.")

    labels = build_reading_document_labels(document)
    template_is_liters = bool(document.template and document.template.is_liters)
    config = _get_reading_document_import_config()

    row_index = 0
    stats = _empty_preview_stats()
    rows = []

    for row in iter_reading_document_rows(uploaded_file):
        row_index += 1
        stats["rows"] += 1

        fields = _build_preview_row_fields(row, labels, template_is_liters=template_is_liters)
        reading_date = parse_reading_document_date(fields["reading_date_raw"])
        if not reading_date:
            stats["skipped_no_date"] += 1
            rows.append(_preview_row(
                row_index=row_index,
                action="skip",
                reason="skipped_no_date",
                fields=fields,
            ))
            continue

        meter, meter_token, comm_module = resolve_reading_document_meter(row, labels)
        reading_date_iso = reading_date.date().isoformat()
        reading_value = fields["reading_value"]
        raw_reading_value = fields["raw_reading_value"]

        if not meter:
            stats["not_found_meter"] += 1
            rows.append(_preview_row(
                row_index=row_index,
                action="not_found",
                fields=fields,
                meter_code=meter_token or comm_module or "",
                comm_module=comm_module,
                reading_date=reading_date_iso,
                reading_value=reading_value,
                raw_reading_value=raw_reading_value,
            ))
            continue

        supply_points = list(meter.supply_points.all())
        if not supply_points:
            stats["no_supply_points"] += 1
            rows.append(_preview_row(
                row_index=row_index,
                action="skip",
                reason="no_supply_points",
                fields=fields,
                meter_code=meter.code,
                comm_module=comm_module,
                reading_date=reading_date_iso,
                reading_value=reading_value,
                raw_reading_value=raw_reading_value,
            ))
            continue

        target = None
        for supply_point in supply_points:
            contract = get_reading_document_target_contract(
                supply_point, config["active_contract_status_token"]
            )
            if contract:
                target = (supply_point, contract)
                if contract.supply_point_default_id == supply_point.id:
                    break

        if not target:
            stats["no_contracts"] += 1
            rows.append(_preview_row(
                row_index=row_index,
                action="skip",
                reason="no_contracts",
                fields=fields,
                meter_code=meter.code,
                comm_module=comm_module,
                reading_date=reading_date_iso,
                reading_value=reading_value,
                raw_reading_value=raw_reading_value,
            ))
            continue

        supply_point, contract = target
        base_date = reading_date.date()
        previous_reading = (
            Reading.objects.filter(
                supply_point=supply_point,
                reading_date__lt=base_date,
                meter=meter,
                contract=contract,
                is_control=False,
            )
            .order_by("-reading_date", "-reading_value")
            .first()
        )
        existing_reading = Reading.objects.filter(
            supply_point=supply_point,
            reading_date=base_date,
            meter=meter,
            contract=contract,
            is_control=fields["is_control"],
            is_initial=False,
        ).first()
        allow_by_period = check_billing_period(
            base_date, supply_point, meter, contract, previous_reading
        )
        prev_reading_invoice = False
        if previous_reading:
            prev_reading_invoice = previous_reading.invoices.filter(
                type_final=config["type_final"]
            ).exclude(
                status__token__in=[
                    config["invoice_status_cancelled"],
                    config["invoice_status_pending"],
                ]
            ).exists()

        previous_reading_value = (
            previous_reading.reading_value if previous_reading else None
        )

        if existing_reading:
            stats["skipped_existing"] += 1
            rows.append(_preview_row(
                row_index=row_index,
                action="skip",
                reason="skipped_existing",
                fields=fields,
                meter_code=meter.code,
                comm_module=comm_module,
                contract_token=contract.token,
                supply_point_id=supply_point.id,
                reading_date=base_date.isoformat(),
                reading_value=reading_value,
                raw_reading_value=raw_reading_value,
                previous_reading_value=previous_reading_value,
            ))
            continue

        if allow_by_period or prev_reading_invoice:
            stats["would_create"] += 1
            action = "would_create"
        else:
            if not previous_reading or previous_reading.reading_date > base_date:
                continue
            stats["would_update"] += 1
            action = "would_update"

        rows.append(_preview_row(
            row_index=row_index,
            action=action,
            fields=fields,
            meter_code=meter.code,
            comm_module=comm_module,
            contract_token=contract.token,
            supply_point_id=supply_point.id,
            reading_date=base_date.isoformat(),
            reading_value=reading_value,
            raw_reading_value=raw_reading_value,
            previous_reading_value=previous_reading_value,
        ))

    return {
        "stats": stats,
        "labels": labels,
        "template_is_liters": template_is_liters,
        "rows": rows,
        "total_rows": len(rows),
        "complete": True,
        "preview_schema_version": PREVIEW_SCHEMA_VERSION,
    }


def _parse_non_negative_int(value, param_name, default=None):
    if value is None or value == "":
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ReadingDocumentPreviewValidationError(
            f"{param_name} ha de ser un enter."
        ) from exc
    if parsed < 0:
        raise ReadingDocumentPreviewValidationError(
            f"{param_name} no pot ser negatiu."
        )
    return parsed


def parse_reading_document_preview_params(query_params=None, data=None):
    """Parse and validate filter/pagination params from query string and/or body."""
    query_params = query_params or {}
    data = data or {}

    def get_param(name):
        if name in query_params and query_params.get(name) not in (None, ""):
            return query_params.get(name)
        if hasattr(data, "get"):
            return data.get(name)
        return None

    action = get_param("action")
    if isinstance(action, str):
        action = action.strip() or None
    if action is not None and action not in VALID_PREVIEW_ACTIONS:
        raise ReadingDocumentPreviewValidationError(
            f"action invàlid. Valors acceptats: {', '.join(sorted(VALID_PREVIEW_ACTIONS))}."
        )

    reason = get_param("reason")
    if isinstance(reason, str):
        reason = reason.strip() or None
    if reason is not None:
        if reason not in VALID_PREVIEW_REASONS:
            raise ReadingDocumentPreviewValidationError(
                f"reason invàlid. Valors acceptats: {', '.join(sorted(VALID_PREVIEW_REASONS))}."
            )
        if action is None:
            action = "skip"
        elif action != "skip":
            raise ReadingDocumentPreviewValidationError(
                "reason només és vàlid amb action=skip."
            )

    page = _parse_non_negative_int(get_param("page"), "page")
    page_size = _parse_non_negative_int(get_param("page_size"), "page_size")
    offset = _parse_non_negative_int(get_param("offset"), "offset")
    max_rows = _parse_non_negative_int(get_param("max_rows"), "max_rows")

    if page is not None:
        if page < 1:
            raise ReadingDocumentPreviewValidationError("page ha de ser >= 1.")
        size = page_size if page_size is not None else (max_rows if max_rows is not None else 25)
        if size < 1:
            raise ReadingDocumentPreviewValidationError("page_size ha de ser >= 1.")
        offset = (page - 1) * size
        max_rows = size
    else:
        if offset is None:
            offset = 0
        if max_rows is None:
            max_rows = page_size if page_size is not None else 25
        if max_rows < 1:
            raise ReadingDocumentPreviewValidationError("max_rows ha de ser >= 1.")

    search = get_param("search")
    if isinstance(search, str):
        search = search.strip() or None

    ordering = get_param("ordering")
    if isinstance(ordering, str):
        ordering = ordering.strip() or None
    if ordering is not None and ordering not in ("row_index", "-row_index"):
        raise ReadingDocumentPreviewValidationError(
            "ordering invàlid. Valors acceptats: row_index, -row_index."
        )

    refresh_raw = get_param("refresh")
    refresh = False
    if refresh_raw is not None:
        if isinstance(refresh_raw, bool):
            refresh = refresh_raw
        else:
            refresh = str(refresh_raw).strip().lower() in ("1", "true", "yes", "on")

    return {
        "action": action,
        "reason": reason,
        "offset": offset,
        "max_rows": max_rows,
        "search": search,
        "ordering": ordering or "row_index",
        "refresh": refresh,
    }


def _row_matches_filter(row, *, action=None, reason=None, search=None):
    if action is not None and row.get("action") != action:
        return False
    if reason is not None and row.get("reason") != reason:
        return False
    if search:
        needle = search.casefold()
        haystacks = [
            str(row.get(field) or "")
            for field in SEARCH_FIELDS
        ]
        if not any(needle in value.casefold() for value in haystacks if value):
            return False
    return True


def _sort_preview_rows(rows, ordering="row_index"):
    reverse = ordering.startswith("-")
    key = ordering.lstrip("-")
    return sorted(rows, key=lambda row: row.get(key) or 0, reverse=reverse)


def slice_reading_document_preview(
    full_preview,
    *,
    action=None,
    reason=None,
    offset=0,
    max_rows=25,
    search=None,
    ordering="row_index",
):
    """Filter + paginate a complete preview. Stats stay global/unfiltered."""
    all_rows = list(full_preview.get("rows") or [])
    filtered_rows = [
        row
        for row in all_rows
        if _row_matches_filter(row, action=action, reason=reason, search=search)
    ]
    filtered_rows = _sort_preview_rows(filtered_rows, ordering=ordering)

    filtered_total = len(filtered_rows)
    page_rows = filtered_rows[offset: offset + max_rows]
    rows_truncated = (offset + len(page_rows)) < filtered_total

    return {
        "stats": full_preview.get("stats") or _empty_preview_stats(),
        "labels": full_preview.get("labels") or {},
        "template_is_liters": bool(full_preview.get("template_is_liters")),
        "rows": page_rows,
        "filtered_total": filtered_total,
        "total_rows": full_preview.get("total_rows", len(all_rows)),
        "rows_truncated": rows_truncated,
        "offset": offset,
        "max_rows": max_rows,
        "action": action,
        "reason": reason,
        "search": search,
        "ordering": ordering,
    }


def is_complete_reading_document_preview(preview):
    if not isinstance(preview, dict):
        return False
    if preview.get("preview_schema_version") != PREVIEW_SCHEMA_VERSION:
        return False
    if preview.get("complete") is True:
        return True
    # Legacy truncated previews must be rebuilt.
    if preview.get("rows_truncated") is True:
        return False
    rows = preview.get("rows")
    total_rows = preview.get("total_rows")
    return isinstance(rows, list) and total_rows is not None and len(rows) == total_rows


def get_or_build_reading_document_preview(document, *, refresh=False):
    cached = document.last_preview
    if not refresh and is_complete_reading_document_preview(cached):
        return cached, False

    preview = build_reading_document_preview(document)
    return preview, True
