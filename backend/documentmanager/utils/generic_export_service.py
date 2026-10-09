import csv
import io
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell


_INTEGER_NUMBER_FORMAT = "0"


def _is_numeric_value(value):
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)


def _decimal_places(value):
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and exponent < 0:
        return min(-exponent, 6)
    return 0


def _number_format_for(value):
    if isinstance(value, Decimal):
        places = _decimal_places(value)
    elif isinstance(value, float) and not value.is_integer():
        places = 2
    else:
        places = 0
    if places == 0:
        return _INTEGER_NUMBER_FORMAT
    return "#,##0." + ("0" * places)


def coerce_export_value(value):
    """
    Turn a cell value into something Excel stores as a number when the source
    value is numeric (int, float, Decimal). Text, including numeric-looking
    tokens, stays text. Empty values become a blank cell.
    Returns (excel_value, number_format or None).
    """
    if value is None or value == "":
        return None, None
    if not _is_numeric_value(value):
        return value, None
    number_format = _number_format_for(value)
    if isinstance(value, Decimal) and _decimal_places(value) == 0:
        return int(value), number_format
    if isinstance(value, float) and value.is_integer():
        return int(value), number_format
    return value, number_format


def _append_export_row(worksheet, values):
    cells = []
    for value in values:
        excel_value, number_format = coerce_export_value(value)
        if number_format is None:
            cells.append(excel_value)
            continue
        cell = WriteOnlyCell(worksheet, value=excel_value)
        cell.number_format = number_format
        cells.append(cell)
    worksheet.append(cells)


def build_export_xlsx_bytes(queryset, columns):
    """
    columns: [(key, header, lambda obj: value), ...]
    XLSX with numeric columns stored as numbers (so Excel can sum them).
    """
    workbook = Workbook(write_only=True)
    worksheet = workbook.create_sheet(title="Export")
    worksheet.append([str(header) for _, header, _ in columns])
    # chunk_size explícit: obligatori quan el queryset porta `prefetch_related`
    # (p. ex. l'export de Meter), si no `iterator()` llença ValueError.
    for obj in queryset.iterator(chunk_size=500):
        _append_export_row(worksheet, [getter(obj) for _, _, getter in columns])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def build_export_csv_bytes(queryset, columns):
    """
    columns: [(key, header, lambda obj: value), ...] (veure ExportConfig.resolve_columns)
    Retorna els bytes del CSV (amb BOM UTF-8) llest per pujar via upload_document.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow([header for _, header, _ in columns])
    # chunk_size explícit: obligatori quan el queryset porta `prefetch_related`
    # (p. ex. l'export de Meter), si no `iterator()` llença ValueError.
    for obj in queryset.iterator(chunk_size=500):
        writer.writerow([getter(obj) for _, _, getter in columns])
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def apply_ordering(queryset, query_params, default_ordering=None):
    ordering = (query_params or {}).get("ordering") or default_ordering
    if ordering:
        queryset = queryset.order_by(*[o.strip() for o in ordering.split(",") if o.strip()])
    return queryset


def resolve_columns(available_columns, default_columns, requested_keys=None):
    """
    available_columns: {key: (header, lambda obj: value)}
    default_columns: llista ordenada de keys quan el front no en demana cap
    requested_keys: llista ordenada de keys demanades (query param `columns=a,b,c`);
                     claus desconegudes s'ignoren; si no en queda cap vàlida, es
                     fa servir default_columns.
    Retorna: [(key, header, getter), ...]
    """
    keys = [k for k in (requested_keys or []) if k in available_columns]
    if not keys:
        keys = default_columns
    return [(key, *available_columns[key]) for key in keys]


def parse_columns_param(query_params):
    requested = (query_params or {}).get("columns")
    if not requested:
        return None
    return [c.strip() for c in requested.split(",") if c.strip()]
