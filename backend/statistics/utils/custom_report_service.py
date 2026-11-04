"""Informes personalitzats: consultes SQL desades pels usuaris (models de django-sql-explorer).

Seguretat:
- Les consultes només s'executen amb la connexió `settings.CUSTOM_REPORTS_DB_ALIAS`, que ha de ser
  un rol de PostgreSQL de només lectura i sense accés a taules sensibles
  (vegeu `manage.py setup_custom_reports_role`). Sense aquesta connexió no s'executa res.
- A més, cada execució va dins una transacció READ ONLY amb `statement_timeout`, que sempre es
  desfà, i la consulta ha de ser una sola sentència que passi la llista negra d'explorer.
- Els paràmetres `$$nom$$` / `$$nom|Etiqueta:valor per defecte$$` es passen com a paràmetres
  enllaçats del driver (mai concatenats al SQL).
"""

import csv
import datetime
import io
import re
import time
import uuid
from decimal import Decimal

import sqlparse
from django.conf import settings
from django.db import DatabaseError, connections, transaction
from django.utils import timezone
from explorer.models import QueryLog
from explorer.utils import extract_params, passes_blacklist, swap_params

PARAM_REGEX = re.compile(r"\$\$([a-z0-9_]+)(?:\|([^\$\:]+))?(?:\:([^\$]+))?\$\$", re.IGNORECASE)

# Taules que el rol d'informes no pot llegir de cap manera.
EXCLUDED_TABLES = (
    "authtoken_token",
    "django_session",
    "explorer_databaseconnection",
)
EXCLUDED_TABLE_PREFIXES = ("explorer_",)
# Taules que es poden llegir excepte aquestes columnes.
SENSITIVE_COLUMNS = {
    "auth_user": ("password",),
    "lecturapp_reading_operator": ("password",),
    "service_companyconfigemail": ("encrypted_password",),
}

EXPORT_FORMATS = ("csv", "xlsx")


class CustomReportError(Exception):
    """Error de validació o d'execució pensat per mostrar-lo a l'usuari.

    `public_message` és l'únic text que arriba al client: es construeix explícitament (missatges
    propis o la línia principal de l'error de PostgreSQL), mai amb traces ni context intern.
    """

    def __init__(self, public_message):
        super().__init__(public_message)
        self.public_message = public_message


class CustomReportNotConfigured(CustomReportError):
    pass


def is_enabled():
    return settings.CUSTOM_REPORTS_DB_ALIAS in connections.databases


def get_connection():
    if not is_enabled():
        raise CustomReportNotConfigured(
            "Custom reports are not configured: set CUSTOM_REPORTS_DATABASE_USER "
            "(read-only role, see `manage.py setup_custom_reports_role`)."
        )
    return connections[settings.CUSTOM_REPORTS_DB_ALIAS]


def get_params(sql):
    """Paràmetres declarats al SQL: [{name, label, default}] en ordre d'aparició."""
    params = extract_params(sql or "")
    return [
        {"name": name, "label": data["label"] or name, "default": data["default"] or ""}
        for name, data in params.items()
    ]


def validate_sql(sql):
    sql = (sql or "").strip()
    if not sql:
        raise CustomReportError("The SQL query is empty.")
    statements = [s for s in sqlparse.split(sql) if s.strip().rstrip(";").strip()]
    if len(statements) != 1:
        raise CustomReportError("Only a single SELECT statement is allowed.")
    ok, failing = passes_blacklist(sql)
    if not ok:
        raise CustomReportError("Forbidden SQL keywords: %s" % ", ".join(failing))
    _check_param_positions(sql)
    return statements[0].strip().rstrip(";").strip()


_PARAM_MARKER = "__custom_report_param__"


def _check_param_positions(sql):
    """Els paràmetres han d'anar com a valors solts, mai dins de cometes, comentaris o identificadors.

    Dins d'un literal (`'$$p$$'`) el valor enllaçat tancaria la cadena i permetria injectar SQL a qui
    només té permís per executar l'informe.
    """
    if not PARAM_REGEX.search(sql):
        return
    marked = PARAM_REGEX.sub(_PARAM_MARKER, sql)
    for token in sqlparse.parse(marked)[0].flatten():
        if _PARAM_MARKER in token.value and not (
            token.value == _PARAM_MARKER and token.ttype in sqlparse.tokens.Name
        ):
            raise CustomReportError(
                "Parameters must be written without quotes and outside comments, "
                "e.g. WHERE code = $$code$$ or LIKE '%' || $$text$$ || '%'."
            )


def build_sql(sql, values=None):
    """Substitueix els `$$param$$` per placeholders del driver.

    Retorna (sql, params) llest per a `cursor.execute`. Els `%` literals s'escapen perquè el driver
    no els interpreti. Els paràmetres sense valor agafen el valor per defecte.
    """
    values = {str(k).lower(): v for k, v in (values or {}).items()}
    declared = extract_params(sql)
    bound = {}
    for name, data in declared.items():
        value = values.get(name)
        if value is None or value == "":
            value = data["default"]
        bound[f"p_{name}"] = "" if value is None else str(value)

    escaped = sql.replace("%", "%%")
    final_sql = PARAM_REGEX.sub(lambda m: f"%(p_{m.group(1).lower()})s", escaped)
    return final_sql, bound


def _json_safe(value):
    if isinstance(value, (bytes, memoryview)):
        return bytes(value).hex()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        if isinstance(value, datetime.datetime) and timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.isoformat()
    if isinstance(value, datetime.timedelta):
        return str(value)
    if isinstance(value, (list, tuple, dict, str, int, float, bool)) or value is None:
        return value
    return str(value)


def execute(sql, values=None, max_rows=None):
    """Executa la consulta i retorna {columns, rows, row_count, truncated, duration_ms}.

    `rows` conserva els tipus de Python (per a l'exportació); vegeu `to_json_rows`.
    """
    clean_sql = validate_sql(sql)
    final_sql, params = build_sql(clean_sql, values)
    connection = get_connection()
    max_rows = max_rows or settings.CUSTOM_REPORTS_MAX_ROWS
    timeout_ms = int(settings.CUSTOM_REPORTS_STATEMENT_TIMEOUT) * 1000

    start = time.monotonic()
    try:
        with transaction.atomic(using=connection.alias):
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute("SET LOCAL statement_timeout = %s", [timeout_ms])
            # Cursor de servidor: només es porten les files necessàries (i PostgreSQL només
            # admet SELECT/VALUES en un DECLARE CURSOR).
            with connection.chunked_cursor() as cursor:
                cursor.execute(final_sql, params)
                rows = [list(r) for r in cursor.fetchmany(max_rows + 1)]
                columns = [col[0] for col in (cursor.description or [])]
            # Mai es confirma res: la transacció es desfà sempre.
            transaction.set_rollback(True, using=connection.alias)
    except DatabaseError as exc:
        raise CustomReportError(_database_error_message(exc)) from exc

    truncated = len(rows) > max_rows
    rows = rows[:max_rows]
    return {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
        "max_rows": max_rows,
        "duration_ms": round((time.monotonic() - start) * 1000, 1),
    }


def _database_error_message(exc):
    """Línia principal (i pista) de l'error de PostgreSQL, sense CONTEXT ni detalls interns.

    És el que necessita qui escriu la consulta (p. ex. `column "x" does not exist`).
    """
    diag = getattr(getattr(exc, "__cause__", None), "diag", None)
    primary = getattr(diag, "message_primary", None)
    if not primary:
        return "The query could not be executed."
    hint = getattr(diag, "message_hint", None)
    return f"{primary} ({hint})" if hint else primary


def to_json_rows(rows):
    return [[_json_safe(v) for v in row] for row in rows]


def run_and_log(sql, values=None, user=None, query=None, max_rows=None):
    """Executa i registra l'execució a `explorer.QueryLog` (també si falla)."""
    log = QueryLog(
        sql=swap_params(sql or "", {p["name"]: (values or {}).get(p["name"]) or p["default"]
                                    for p in get_params(sql)}),
        query=query,
        run_by_user=user if user and user.is_authenticated else None,
    )
    try:
        result = execute(sql, values, max_rows=max_rows)
    except CustomReportError as exc:
        if not isinstance(exc, CustomReportNotConfigured):
            log.success = False
            log.error = str(exc)
            log.save()
        raise
    log.duration = result["duration_ms"]
    log.save()
    return result


def _excel_value(value):
    if isinstance(value, datetime.datetime) and timezone.is_aware(value):
        return timezone.localtime(value).replace(tzinfo=None)
    if isinstance(value, datetime.time) and value.tzinfo is not None:
        return value.replace(tzinfo=None)
    if isinstance(value, (Decimal, int, float, bool, datetime.date, datetime.datetime, datetime.time)) \
            or value is None:
        return value
    value = _json_safe(value)
    return value if isinstance(value, str) else str(value)


def _csv_safe(value):
    """Evita que Excel interpreti com a fórmula un text de la BD (=, +, -, @, tab, CR)."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def export(result, file_format, title="report"):
    """Retorna (bytes, content_type, filename)."""
    safe_title = re.sub(r"[^\w\-]+", "_", title or "report").strip("_")[:80] or "report"
    stamp = timezone.localtime().strftime("%Y%m%d_%H%M")
    if file_format == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";")
        writer.writerow(result["columns"])
        for row in result["rows"]:
            writer.writerow(["" if v is None else _csv_safe(_json_safe(v)) for v in row])
        content = ("﻿" + buffer.getvalue()).encode("utf-8")
        return content, "text/csv; charset=utf-8", f"{safe_title}_{stamp}.csv"

    if file_format == "xlsx":
        from openpyxl import Workbook

        from openpyxl.cell import WriteOnlyCell

        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet(title=safe_title[:31] or "report")

        def cell(value):
            # openpyxl converteix en fórmula qualsevol text que comenci per "=": es força a text.
            value = _excel_value(value)
            c = WriteOnlyCell(sheet, value=value)
            if isinstance(value, str) and value.startswith("="):
                c.data_type = "s"
            return c

        sheet.append([cell(str(c)) for c in result["columns"]])
        for row in result["rows"]:
            sheet.append([cell(v) for v in row])
        buffer = io.BytesIO()
        workbook.save(buffer)
        return (
            buffer.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            f"{safe_title}_{stamp}.xlsx",
        )

    raise CustomReportError(f"Unsupported export format: {file_format}")


def get_schema():
    """Taules i columnes visibles pel rol d'informes: [{table, columns: [{name, type}]}]."""
    connection = get_connection()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT c.table_name, c.column_name, c.data_type, t.table_type
            FROM information_schema.columns c
            JOIN information_schema.tables t
              ON t.table_schema = c.table_schema AND t.table_name = c.table_name
            WHERE c.table_schema = current_schema()
            ORDER BY c.table_name, c.ordinal_position
            """
        )
        rows = cursor.fetchall()
    schema = {}
    for table, column, data_type, table_type in rows:
        if table in EXCLUDED_TABLES or table.startswith(EXCLUDED_TABLE_PREFIXES):
            continue
        entry = schema.setdefault(
            table, {"table": table, "is_view": table_type == "VIEW", "columns": []}
        )
        entry["columns"].append({"name": column, "type": data_type})
    return list(schema.values())
