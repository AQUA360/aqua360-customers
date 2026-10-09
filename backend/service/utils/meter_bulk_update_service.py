"""
Update massiva de Meter des de CSV/Excel: parse, preview i apply.
1a columna = meter.code; resta = camps a actualitzar (cel·les buides = no tocar).
"""
import csv
import io
from datetime import datetime

from django.db import transaction

from service.models import Meter, MeterCaliber, MeterStatus

# Camps escalars / FK simples actualitzables
UPDATABLE_FIELDS = frozenset({
    'code2',
    'is_compound',
    'is_property',
    'is_general',
    'manufacturer',
    'manufacturing_year',
    'model',
    'comm_module',
    'comm_module_type',
    'comm_technology',
    'network_provider',
    'installation_at',
    'uninstallation_at',
    'digits',
    'latitude',
    'longitude',
    'has_remote_reading',
    'remote_reading_type',
    'has_ever_been_remote',
    'status',
    'caliber',
})

BOOLEAN_FIELDS = frozenset({
    'is_compound',
    'is_property',
    'is_general',
    'has_remote_reading',
    'has_ever_been_remote',
})

INTEGER_FIELDS = frozenset({'manufacturing_year', 'digits'})
FLOAT_FIELDS = frozenset({'latitude', 'longitude'})
DATE_FIELDS = frozenset({'installation_at', 'uninstallation_at'})
FK_FIELDS = frozenset({'status', 'caliber'})

CODE_HEADER_ALIASES = frozenset({
    'code',
    'meter.code',
    'meter_code',
    'metercode',
})

# Alias capçalera (normalitzada) → camp model
HEADER_ALIASES = {
    'code2': 'code2',
    'iscompound': 'is_compound',
    'is_compound': 'is_compound',
    'isproperty': 'is_property',
    'is_property': 'is_property',
    'isgeneral': 'is_general',
    'is_general': 'is_general',
    'manufacturer': 'manufacturer',
    'manufacturingyear': 'manufacturing_year',
    'manufacturing_year': 'manufacturing_year',
    'model': 'model',
    'commmodule': 'comm_module',
    'comm_module': 'comm_module',
    'commmoduletype': 'comm_module_type',
    'comm_module_type': 'comm_module_type',
    'commtechnology': 'comm_technology',
    'comm_technology': 'comm_technology',
    'networkprovider': 'network_provider',
    'network_provider': 'network_provider',
    'installationat': 'installation_at',
    'installation_at': 'installation_at',
    'uninstallationat': 'uninstallation_at',
    'uninstallation_at': 'uninstallation_at',
    'digits': 'digits',
    'latitude': 'latitude',
    'longitude': 'longitude',
    'hasremotereading': 'has_remote_reading',
    'has_remote_reading': 'has_remote_reading',
    'remotereadingtype': 'remote_reading_type',
    'remote_reading_type': 'remote_reading_type',
    'haseverbeenremote': 'has_ever_been_remote',
    'has_ever_been_remote': 'has_ever_been_remote',
    'status': 'status',
    'status[token]': 'status',
    'statustoken': 'status',
    'caliber': 'caliber',
    'caliber[token]': 'caliber',
    'calibertoken': 'caliber',
}

REMOTE_READING_TYPES = frozenset({'SMART_METERING', 'OTHER'})


class MeterBulkUpdateError(Exception):
    """Fitxer o estructura invàlida (HTTP 400)."""


def _normalize_header(raw):
    if raw is None:
        return ''
    return str(raw).strip().lower().replace(' ', '').replace('-', '_')


def _resolve_field_from_header(header):
    key = _normalize_header(header)
    if not key:
        return None
    if key in CODE_HEADER_ALIASES or key == 'code':
        return None  # columna clau, no camp a actualitzar
    return HEADER_ALIASES.get(key)


def _cell_empty(value):
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _parse_bool(raw):
    text = str(raw).strip().lower()
    if text in ('true', '1', 'yes', 'y', 'sí', 'si'):
        return True
    if text in ('false', '0', 'no', 'n'):
        return False
    raise ValueError(f"Valor booleà invàlid: {raw!r}")


def _parse_date(raw):
    text = str(raw).strip()
    if hasattr(raw, 'date') and not isinstance(raw, str):
        # datetime from openpyxl
        return raw.date() if hasattr(raw, 'hour') else raw
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Data invàlida (espera YYYY-MM-DD): {raw!r}")


def _normalize_caliber_token(raw_value):
    if raw_value is None:
        return None
    caliber_value = str(raw_value).strip()
    if not caliber_value:
        return None
    normalized_value = caliber_value.replace(',', '.')
    try:
        numeric_value = float(normalized_value)
        if numeric_value <= 0:
            return None
        if numeric_value.is_integer():
            return str(int(numeric_value))
    except ValueError:
        pass
    return normalized_value


def _resolve_status(raw):
    text = str(raw).strip()
    if not text:
        return None
    status = MeterStatus.objects.filter(token=text).first()
    if status:
        return status
    status = MeterStatus.objects.filter(name=text).first()
    if status:
        return status
    raise ValueError(f"MeterStatus no trobat: {text!r}")


def _resolve_caliber(raw):
    token = _normalize_caliber_token(raw)
    if not token:
        raise ValueError(f"Caliber invàlid: {raw!r}")
    caliber = MeterCaliber.objects.filter(token=token).first()
    if caliber:
        return caliber
    caliber = MeterCaliber.objects.filter(name=token).first()
    if caliber:
        return caliber
    # Fallback: name sense normalitzar
    text = str(raw).strip()
    caliber = MeterCaliber.objects.filter(name=text).first()
    if caliber:
        return caliber
    raise ValueError(f"MeterCaliber no trobat: {raw!r}")


def _coerce_field_value(field, raw):
    if field in BOOLEAN_FIELDS:
        return _parse_bool(raw)
    if field in INTEGER_FIELDS:
        text = str(raw).strip()
        try:
            return int(float(text.replace(',', '.')))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{field} ha de ser un enter: {raw!r}") from exc
    if field in FLOAT_FIELDS:
        text = str(raw).strip().replace(',', '.')
        try:
            return float(text)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{field} ha de ser un número: {raw!r}") from exc
    if field in DATE_FIELDS:
        return _parse_date(raw)
    if field == 'status':
        return _resolve_status(raw)
    if field == 'caliber':
        return _resolve_caliber(raw)
    if field == 'remote_reading_type':
        text = str(raw).strip().upper()
        if text not in REMOTE_READING_TYPES:
            raise ValueError(
                f"remote_reading_type ha de ser un de {sorted(REMOTE_READING_TYPES)}: {raw!r}"
            )
        return text
    # CharField i similars
    return str(raw).strip() if isinstance(raw, str) else str(raw).strip()


def _serialize_value(value):
    if value is None:
        return None
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if isinstance(value, MeterStatus):
        return {'id': value.id, 'token': value.token, 'name': value.name}
    if isinstance(value, MeterCaliber):
        return {'id': value.id, 'token': value.token, 'name': value.name}
    return value


def _current_field_value(meter, field):
    if field == 'status':
        return meter.status
    if field == 'caliber':
        return meter.caliber
    return getattr(meter, field)


def _values_equal(old, new):
    if old is None and new is None:
        return True
    if isinstance(old, (MeterStatus, MeterCaliber)) or isinstance(new, (MeterStatus, MeterCaliber)):
        old_id = getattr(old, 'id', None) if old is not None else None
        new_id = getattr(new, 'id', None) if new is not None else None
        return old_id == new_id
    return old == new


def _read_file_bytes(uploaded_file):
    if hasattr(uploaded_file, 'seek'):
        uploaded_file.seek(0)
    content = uploaded_file.read()
    if isinstance(content, str):
        content = content.encode('utf-8')
    return content


def _parse_csv_bytes(content):
    text = content.decode('utf-8-sig')
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=';,')
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ';' if sample.count(';') >= sample.count(',') else ','

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        raise MeterBulkUpdateError("El fitxer CSV està buit.")
    return rows


def _parse_xlsx_bytes(content):
    try:
        import openpyxl
    except ImportError as exc:
        raise MeterBulkUpdateError("openpyxl no està disponible per llegir Excel.") from exc

    workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    sheet = workbook.active
    rows = []
    for row in sheet.iter_rows(values_only=True):
        rows.append([('' if cell is None else cell) for cell in row])
    workbook.close()
    # Treure files totalment buides al final
    while rows and all(_cell_empty(c) for c in rows[-1]):
        rows.pop()
    if not rows:
        raise MeterBulkUpdateError("El fitxer Excel està buit.")
    return rows


def _detect_and_parse(uploaded_file):
    name = (getattr(uploaded_file, 'name', '') or '').lower()
    content = _read_file_bytes(uploaded_file)

    if name.endswith(('.xlsx', '.xls')):
        return _parse_xlsx_bytes(content)
    if name.endswith('.csv'):
        return _parse_csv_bytes(content)

    # Sense extensió clara: provar CSV, després Excel
    try:
        return _parse_csv_bytes(content)
    except Exception:
        try:
            return _parse_xlsx_bytes(content)
        except Exception as exc:
            raise MeterBulkUpdateError(
                "Format de fitxer no suportat. Usa .csv, .xlsx o .xls."
            ) from exc


def parse_meter_bulk_file(uploaded_file):
    """
    Retorna (columns, rows) on:
    - columns: llista de camps model detectats (ordre)
    - rows: [{row, code, values: {field: raw}}, ...]
    """
    raw_rows = _detect_and_parse(uploaded_file)
    header = raw_rows[0]
    if not header or all(_cell_empty(c) for c in header):
        raise MeterBulkUpdateError("Falta la fila de capçaleres.")

    # Columna de code
    code_col_index = 0
    for idx, col in enumerate(header):
        if _normalize_header(col) in CODE_HEADER_ALIASES or _normalize_header(col) == 'code':
            code_col_index = idx
            break

    field_by_col = {}
    unknown_headers = []
    columns = []
    for idx, col in enumerate(header):
        if idx == code_col_index:
            continue
        if _cell_empty(col):
            continue
        field = _resolve_field_from_header(col)
        if not field:
            unknown_headers.append(str(col).strip())
            continue
        if field not in UPDATABLE_FIELDS:
            unknown_headers.append(str(col).strip())
            continue
        field_by_col[idx] = field
        if field not in columns:
            columns.append(field)

    if unknown_headers:
        raise MeterBulkUpdateError(
            f"Columnes no reconegudes o no actualitzables: {', '.join(unknown_headers)}"
        )
    if not columns:
        raise MeterBulkUpdateError(
            "No hi ha cap columna actualitzable. La primera columna ha de ser code "
            "i la resta camps del Meter (ex. code2, status, has_remote_reading)."
        )

    parsed_rows = []
    for row_number, raw in enumerate(raw_rows[1:], start=2):
        # Extendre fila curta
        cells = list(raw) if raw else []
        while len(cells) < len(header):
            cells.append('')

        if all(_cell_empty(c) for c in cells):
            continue

        code_raw = cells[code_col_index] if code_col_index < len(cells) else ''
        code = str(code_raw).strip() if code_raw is not None else ''
        values = {}
        for col_idx, field in field_by_col.items():
            cell = cells[col_idx] if col_idx < len(cells) else ''
            if _cell_empty(cell):
                continue
            values[field] = cell

        parsed_rows.append({
            'row': row_number,
            'code': code,
            'values': values,
        })

    if not parsed_rows:
        raise MeterBulkUpdateError("El fitxer no conté files de dades.")

    return columns, parsed_rows


def _build_row_result(columns, parsed_rows, *, apply=False):
    codes = [r['code'] for r in parsed_rows if r['code']]
    meters = list(
        Meter.objects.filter(code__in=codes).select_related('status', 'caliber')
    )
    meters_by_code = {}
    duplicate_codes = set()
    for meter in meters:
        if not meter.code:
            continue
        if meter.code in meters_by_code:
            duplicate_codes.add(meter.code)
        else:
            meters_by_code[meter.code] = meter

    # Codes que es repeteixen al fitxer (no a BD): el preview/confirm processen
    # seqüencialment; la 2a aparició pot quedar "unchanged" si el valor ja s'ha aplicat.
    code_counts = {}
    for item in parsed_rows:
        code = item.get('code')
        if code:
            code_counts[code] = code_counts.get(code, 0) + 1
    duplicate_codes_in_file = sorted(c for c, n in code_counts.items() if n > 1)

    updates = []
    unchanged = []
    not_found = []
    errors = []
    seen_not_found = set()

    for item in parsed_rows:
        row_num = item['row']
        code = item['code']
        raw_values = item['values']

        if not code:
            errors.append({
                'row': row_num,
                'code': code or None,
                'message': "Falta el code del comptador.",
            })
            continue

        if code in duplicate_codes:
            errors.append({
                'row': row_num,
                'code': code,
                'message': f"Hi ha més d'un Meter amb code {code!r}.",
            })
            continue

        meter = meters_by_code.get(code)
        if not meter:
            if code not in seen_not_found:
                not_found.append(code)
                seen_not_found.add(code)
            continue

        if not raw_values:
            unchanged.append({
                'row': row_num,
                'code': code,
                'meter_id': meter.id,
            })
            continue

        coerced = {}
        row_errors = []
        for field, raw in raw_values.items():
            try:
                coerced[field] = _coerce_field_value(field, raw)
            except ValueError as exc:
                row_errors.append(str(exc))

        if row_errors:
            errors.append({
                'row': row_num,
                'code': code,
                'message': '; '.join(row_errors),
            })
            continue

        changes = {}
        for field, new_value in coerced.items():
            old_value = _current_field_value(meter, field)
            if not _values_equal(old_value, new_value):
                changes[field] = {
                    'old': _serialize_value(old_value),
                    'new': _serialize_value(new_value),
                }

        if not changes:
            entry = {
                'row': row_num,
                'code': code,
                'meter_id': meter.id,
            }
            if code in code_counts and code_counts[code] > 1:
                entry['reason'] = 'already_updated_earlier_in_file'
            unchanged.append(entry)
            continue

        update_entry = {
            'row': row_num,
            'code': code,
            'meter_id': meter.id,
            'changes': changes,
        }

        # Aplicar en memòria sempre (preview i confirm) perquè files posteriors
        # amb el mateix code vegin l'estat efectiu després de files anteriors.
        for field, new_value in coerced.items():
            if field in changes:
                setattr(meter, field, new_value)
        if meter.has_remote_reading and not meter.has_ever_been_remote:
            meter.has_ever_been_remote = True

        if apply:
            meter.save()
            update_entry['applied'] = True

        updates.append(update_entry)

    stats_key = 'updated' if apply else 'to_update'
    return {
        'stats': {
            'total_rows': len(parsed_rows),
            stats_key: len(updates),
            'unchanged': len(unchanged),
            'not_found': len(not_found),
            'errors': len(errors),
            'duplicate_codes_in_file': len(duplicate_codes_in_file),
        },
        'columns': columns,
        'updates': updates,
        'unchanged': unchanged,
        'not_found': not_found,
        'errors': errors,
        'duplicate_codes_in_file': duplicate_codes_in_file,
    }


def build_preview(uploaded_file):
    columns, parsed_rows = parse_meter_bulk_file(uploaded_file)
    result = _build_row_result(columns, parsed_rows, apply=False)
    # Unificar clau to_update també si confirm usa updated
    if 'to_update' not in result['stats']:
        result['stats']['to_update'] = result['stats'].get('updated', 0)
    return result


def apply_updates(uploaded_file):
    columns, parsed_rows = parse_meter_bulk_file(uploaded_file)
    with transaction.atomic():
        result = _build_row_result(columns, parsed_rows, apply=True)
    # Afegir to_update per compatibilitat amb el mateix shape de preview
    result['stats']['to_update'] = result['stats'].get('updated', 0)
    return result
