"""Versió PDF de presentació dels informes Excel.

Converteix de forma genèrica qualsevol llibre openpyxl generat pels informes
(statistics/utils/report_*_service.py) a un PDF net, pensat per presentar
(p. ex. a un consell d'administració), amb la plantilla
`report_pdf_template.html` (personalitzable per client amb
`report_pdf_template_personalized.html`).

No cal tocar cap generador: run_report_task obre el context `pdf_export()` i
`save_report` (statistics/views/reports_views.py) crida
`convert_report_content_to_pdf()` abans de pujar el document.

Heurística de conversió, per full:
  * es descarten files i columnes ocultes o buides;
  * el full es parteix en blocs separats per files buides; cada bloc és una taula;
  * la primera fila d'un bloc amb només textos (i almenys dues cel·les) és la
    capçalera i es repeteix a cada pàgina;
  * les files abans de la primera taula amb una sola cel·la són el títol/subtítols;
  * les files en negreta (subtotals, totals) es destaquen;
  * les cel·les combinades es respecten (colspan/rowspan);
  * els números es formaten segons el number_format de la cel·la.
"""
import datetime
import decimal
import logging
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from io import BytesIO

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)

PDF_TEMPLATE = "report_pdf_template.html"

# Límits per a un informe "de presentació": per sobre d'això el PDF no és útil
# (i xhtml2pdf triga massa); l'usuari ha de fer servir l'Excel.
MAX_PDF_ROWS = 5000
MAX_PDF_COLUMNS = 40

_pdf_export = ContextVar("report_pdf_export", default=None)


class ReportTooLargeForPdf(Exception):
    """L'informe supera els límits raonables per a un PDF."""


class ReportPdfError(Exception):
    """No s'ha pogut generar el PDF de l'informe."""


@contextmanager
def pdf_export(title=None, filters_display=None):
    """Dins d'aquest context, save_report desa l'informe en PDF en lloc d'Excel."""
    options = {
        "title": title,
        "filters_display": filters_display or [],
        # Error de conversió: els generadors capturen les excepcions de
        # save_report, així que run_report_task el recupera d'aquí.
        "error": None,
    }
    token = _pdf_export.set(options)
    try:
        yield options
    finally:
        _pdf_export.reset(token)


def get_pdf_export_options():
    """Opcions del context pdf_export() actiu, o None si no s'ha demanat PDF."""
    return _pdf_export.get()


# ---------------------------------------------------------------------------
# Format de valors
# ---------------------------------------------------------------------------

_HYPERLINK_RE = re.compile(r'^=HYPERLINK\(\s*"[^"]*"\s*[,;]\s*"([^"]*)"\s*\)\s*$', re.IGNORECASE)
_QUOTED_SECTION_RE = re.compile(r'"[^"]*"|\[[^\]]*\]|\\.')


def _uses_english_separators():
    return (settings.LANGUAGE_CODE or "").lower().startswith("en")


def _format_number(value, decimals, thousands, min_decimals=None):
    text = f"{value:,.{decimals}f}" if thousands else f"{value:.{decimals}f}"
    if min_decimals is not None and min_decimals < decimals:
        # Decimals opcionals ('#' a Excel): fora els zeros finals fins al mínim.
        integer, _sep, fraction = text.partition(".")
        fraction = fraction.rstrip("0")
        fraction += "0" * max(0, min_decimals - len(fraction))
        text = f"{integer}.{fraction}" if fraction else integer
    if _uses_english_separators():
        return text
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _number_format_info(number_format):
    """(decimals, min_decimals, thousands, percent, suffix) a partir d'un format d'Excel.

    Només s'interpreta la primera secció (valors positius); n'hi ha prou per als
    formats que fan servir els informes ('#,##0.00', '0.00%', '#,##0.00 €'...).
    """
    fmt = (number_format or "General").split(";")[0]
    if fmt == "General":
        return None
    literal_suffix = ""
    if "€" in fmt:
        literal_suffix = " €"
    elif "$" in fmt:
        literal_suffix = " $"
    clean = _QUOTED_SECTION_RE.sub("", fmt)
    percent = "%" in clean
    thousands = "," in clean.split(".")[0] and "#" in clean
    decimals = min_decimals = 0
    if "." in clean:
        digits = re.match(r"[0#]*", clean.split(".", 1)[1]).group(0)
        decimals = len(digits)
        min_decimals = digits.count("0")
    return decimals, min_decimals, thousands, percent, literal_suffix


def _is_date_format(number_format):
    fmt = _QUOTED_SECTION_RE.sub("", (number_format or "").lower())
    return any(token in fmt for token in ("d", "m", "y", "h", "s")) and "general" not in fmt and "0" not in fmt


def format_cell_value(value, number_format="General"):
    """Text a mostrar per a un valor de cel·la, i si s'ha d'alinear a la dreta."""
    if value is None:
        return "", False
    if isinstance(value, bool):
        return (_("Sí") if value else _("No")), False
    if isinstance(value, datetime.datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        fmt = (number_format or "").lower()
        if (value.hour or value.minute) and ("h" in fmt or not _is_date_format(fmt)):
            return value.strftime("%d/%m/%Y %H:%M"), False
        return value.strftime("%d/%m/%Y"), False
    if isinstance(value, datetime.date):
        return value.strftime("%d/%m/%Y"), False
    if isinstance(value, datetime.time):
        return value.strftime("%H:%M"), False
    if isinstance(value, (int, float, decimal.Decimal)):
        info = _number_format_info(number_format)
        if info is None:
            # 'General': els enters poden ser codis o anys, sense separador de milers.
            if isinstance(value, int) or (isinstance(value, decimal.Decimal) and value == value.to_integral_value()):
                return str(int(value)), True
            return _format_number(float(value), 2, True), True
        decimals, min_decimals, thousands, percent, suffix = info
        number = float(value) * (100 if percent else 1)
        text = _format_number(number, decimals, thousands, min_decimals)
        return f"{text}{' %' if percent else ''}{suffix}", True
    text = str(value)
    if text.startswith("="):
        match = _HYPERLINK_RE.match(text)
        # Les fórmules no tenen valor calculat en un llibre generat amb openpyxl.
        return (match.group(1) if match else ""), False
    return text, False


# ---------------------------------------------------------------------------
# Lectura del llibre
# ---------------------------------------------------------------------------

def _load_workbook(content):
    """Llibre openpyxl a partir del contingut que rep save_report, o None si no és un Excel."""
    from openpyxl import Workbook, load_workbook

    if isinstance(content, Workbook):
        return content
    raw = None
    if isinstance(content, (bytes, bytearray)):
        raw = bytes(content)
    elif hasattr(content, "read"):
        raw = content.read()
        if hasattr(content, "seek"):
            content.seek(0)
    if not raw:
        return None
    try:
        return load_workbook(BytesIO(raw), data_only=True)
    except Exception:
        return None


def _is_bold(cell):
    return bool(cell.font and cell.font.b)


def _has_fill(cell):
    fill = cell.fill
    if not fill or fill.fill_type in (None, "none"):
        return False
    color = getattr(fill.fgColor, "rgb", None)
    return isinstance(color, str) and color.upper() not in ("00000000", "FFFFFFFF")


def _sheet_to_blocks(ws):
    """Estructura renderitzable d'un full: títols i taules (llistes de files de cel·les)."""
    from openpyxl.utils import get_column_letter

    max_row = ws.max_row or 0
    max_col = ws.max_column or 0
    if not max_row or not max_col:
        return None

    hidden_cols = {
        col for col in range(1, max_col + 1)
        if ws.column_dimensions[get_column_letter(col)].hidden
    }
    hidden_rows = {row for row, dim in ws.row_dimensions.items() if dim.hidden}

    # Cel·les combinades: la de dalt a l'esquerra porta el span, la resta s'amaguen.
    merged_origin = {}
    merged_covered = set()
    for merged in ws.merged_cells.ranges:
        merged_origin[(merged.min_row, merged.min_col)] = merged
        for row in range(merged.min_row, merged.max_row + 1):
            for col in range(merged.min_col, merged.max_col + 1):
                if (row, col) != (merged.min_row, merged.min_col):
                    merged_covered.add((row, col))

    grid = {}
    used_cols = set()
    used_rows = []
    for row_cells in ws.iter_rows(min_row=1, max_row=max_row, max_col=max_col):
        row_idx = row_cells[0].row
        if row_idx in hidden_rows:
            continue
        has_value = False
        for cell in row_cells:
            if cell.column in hidden_cols or (row_idx, cell.column) in merged_covered:
                continue
            text, numeric = format_cell_value(cell.value, cell.number_format)
            if text.strip() == "":
                continue
            grid[(row_idx, cell.column)] = {
                "text": text,
                "numeric": numeric,
                "bold": _is_bold(cell),
                "filled": _has_fill(cell),
                "is_text": isinstance(cell.value, str),
                "size": float(cell.font.sz) if cell.font and cell.font.sz else 11.0,
            }
            used_cols.add(cell.column)
            has_value = True
        if has_value:
            used_rows.append(row_idx)

    if not used_rows:
        return None

    columns = sorted(used_cols)
    if len(columns) > MAX_PDF_COLUMNS:
        raise ReportTooLargeForPdf(
            _("L'informe té massa columnes (%(count)s) per generar-ne un PDF. Descarregueu-lo en Excel.")
            % {"count": len(columns)}
        )
    column_count = len(columns)
    col_pos = {col: idx for idx, col in enumerate(columns)}
    used_rows_set = set(used_rows)

    def span_for(row_idx, col):
        merged = merged_origin.get((row_idx, col))
        if not merged:
            return 1, 1
        colspan = sum(1 for c in range(merged.min_col, merged.max_col + 1) if c in col_pos)
        rowspan = sum(
            1 for r in range(merged.min_row, merged.max_row + 1)
            if r not in hidden_rows and r in used_rows_set
        )
        return max(colspan, 1), max(rowspan, 1)

    def make_row(row_idx, blank_before):
        cells = []
        for col in columns:
            if (row_idx, col) in merged_covered:
                continue
            data = grid.get((row_idx, col))
            colspan, rowspan = span_for(row_idx, col) if data else (1, 1)
            cells.append({
                "text": data["text"] if data else "",
                "numeric": data["numeric"] if data else False,
                "bold": data["bold"] if data else False,
                "filled": data["filled"] if data else False,
                "is_text": data["is_text"] if data else True,
                "size": data["size"] if data else 0.0,
                "empty": data is None,
                "colspan": colspan,
                "rowspan": rowspan,
                "col_index": col_pos[col],
            })
        # Les cel·les buides que queden dins d'un colspan anterior no s'han de pintar.
        visible = []
        skip_until = -1
        for cell in cells:
            if cell["col_index"] <= skip_until:
                continue
            visible.append(cell)
            skip_until = cell["col_index"] + cell["colspan"] - 1
        filled = [c for c in visible if not c["empty"]]
        return {
            "cells": visible,
            "filled": filled,
            "blank_before": blank_before,
            "text_only": all(c["is_text"] for c in filled),
            "bold": sum(1 for c in filled if c["bold"]) * 2 > len(filled),
            "styled": sum(1 for c in filled if c["bold"] or c["filled"]) * 2 > len(filled),
            "size": max(c["size"] for c in filled),
        }

    rows = []
    previous = None
    for row_idx in used_rows:
        blank_before = previous is not None and any(
            r not in hidden_rows for r in range(previous + 1, row_idx)
        )
        rows.append(make_row(row_idx, blank_before))
        previous = row_idx

    def covered_columns(row):
        covered = set()
        for cell in row["filled"]:
            covered.update(range(cell["col_index"], cell["col_index"] + cell["colspan"]))
        return covered

    def looks_like_header(row, idx, strict=True):
        if len(row["filled"]) < 2 or not row["text_only"]:
            return False
        if not strict:
            return True
        if not row["styled"]:
            return False
        # Una capçalera té títol sobre les columnes amb xifres de les files que la
        # segueixen; un títol de grup ("Ús: X | Nom") no.
        for following in rows[idx + 1:idx + 12]:
            numeric_cols = {c["col_index"] for c in following["filled"] if c["numeric"]}
            if len(numeric_cols) >= 2:
                return numeric_cols <= covered_columns(row)
        return len(row["filled"]) * 2 >= column_count

    def is_caption(row):
        return len(row["filled"]) == 1 and row["filled"][0]["is_text"]

    # Files que obren una taula nova: una capçalera amb estil (negreta o fons) que
    # cobreixi almenys la meitat de columnes, a l'inici, després d'una fila buida o
    # d'un títol. Una fila buida sola NO obre taula: el bloc continua l'anterior.
    header_starts = set()
    started = False
    for idx, row in enumerate(rows):
        prev_caption = idx > 0 and not row["blank_before"] and is_caption(rows[idx - 1])
        if (
            looks_like_header(row, idx)
            and idx + 1 < len(rows)
            and (not started or row["blank_before"] or prev_caption)
        ):
            header_starts.add(idx)
            started = True
    if not header_starts:
        # Informes sense capçalera amb estil: la primera fila només de textos.
        for idx, row in enumerate(rows):
            if not is_caption(row) and looks_like_header(row, idx, strict=False) and idx + 1 < len(rows):
                header_starts.add(idx)
                break

    titles = []
    tables = []
    current = None
    pending = []

    def flush_pending_into_body():
        if current is not None:
            current["body"].extend(pending)
        else:
            titles.extend(" · ".join(c["text"] for c in r["filled"]) for r in pending)
        pending.clear()

    for idx, row in enumerate(rows):
        if idx in header_starts:
            # Els títols just abans de la capçalera són de la taula nova.
            captions = [r["filled"][0]["text"] for r in pending if is_caption(r)]
            if current is None:
                titles.extend(
                    " · ".join(c["text"] for c in r["filled"]) for r in pending if not is_caption(r)
                )
                if not tables and not titles and captions:
                    titles.extend(captions)
                    captions = []
            pending.clear()
            current = {"header": [row], "body": [], "captions": captions}
            tables.append(current)
            continue
        if is_caption(row) or (current is None and len(titles) + len(pending) < 6):
            if row["blank_before"] and pending and current is not None:
                flush_pending_into_body()
            pending.append(row)
            continue
        if current is None:
            # Massa preàmbul sense capçalera: tot plegat és una taula sense capçalera.
            current = {"header": [], "body": [], "captions": []}
            tables.append(current)
        flush_pending_into_body()
        current["body"].append(row)
    if pending:
        if current is None and not tables:
            titles.extend(" · ".join(c["text"] for c in r["filled"]) for r in pending)
        else:
            flush_pending_into_body()

    built = []
    for table in tables:
        if table["header"] or table["body"]:
            built.extend(_build_tables(table, column_count))

    return {"name": ws.title, "titles": titles[:6], "tables": built, "column_count": column_count}


# Mida mínima mitjana dels grups per partir una taula per grups (amb el títol del
# grup repetit a cada pàgina); amb grups més petits només es destaquen.
MIN_ROWS_PER_GROUP = 5


def _row_css(row, column_count):
    """section (títol de grup), total (subtotals/totals) o res."""
    filled = row["filled"]
    if not filled or not row["bold"]:
        return ""
    # Títol de grup: en negreta i sense xifres (com a molt un codi a la primera cel·la).
    if not any(c["numeric"] for c in filled[1:]) and (len(filled) > 1 or filled[0]["is_text"]):
        return "section"
    return "total"


def _build_tables(table, column_count):
    """Estils de fila, amplades i partició per grups d'una taula del full."""
    header = [r["cells"] for r in table["header"]]

    body = []
    for row in table["body"]:
        css = _row_css(row, column_count)
        cells = row["cells"]
        if len(row["filled"]) == 1 and column_count > 2:
            # Una sola cel·la (títol de grup o nota): ocupa tota l'amplada.
            cells = [dict(row["filled"][0], colspan=column_count, rowspan=1, col_index=0)]
        if row["blank_before"] and body:
            body.append({"cells": [], "css": "spacer", "size": 0})
        body.append({"cells": cells, "css": css, "size": row["size"]})

    # Nivells de grup: els títols de grup amb la lletra més gran són el nivell principal.
    section_sizes = [r["size"] for r in body if r["css"] == "section"]
    top_size = max(section_sizes) if section_sizes else None
    for row in body:
        if row["css"] == "section" and row["size"] < top_size:
            row["css"] = "subsection"

    # Capçaleres de columnes numèriques alineades a la dreta, com les dades.
    numeric_votes = [0] * column_count
    text_votes = [0] * column_count
    for row in body:
        if row["css"] in ("section", "subsection", "spacer"):
            continue
        for cell in row["cells"]:
            if cell["colspan"] == 1 and not cell["empty"]:
                if cell["numeric"]:
                    numeric_votes[cell["col_index"]] += 1
                else:
                    text_votes[cell["col_index"]] += 1
    for row in header:
        for cell in row:
            if cell["colspan"] == 1:
                cell["numeric"] = numeric_votes[cell["col_index"]] > text_votes[cell["col_index"]]

    # Amplades proporcionals a la llargada del text (amb límits), en %.
    weights = [4] * column_count
    for row in header + [r["cells"] for r in body[:300]]:
        for cell in row:
            if cell["colspan"] == 1:
                weights[cell["col_index"]] = max(weights[cell["col_index"]], min(len(cell["text"]), 40))
    total = sum(weights) or 1
    widths = [w * 100 / total for w in weights]

    def set_widths(cells):
        for cell in cells:
            # Com a text: la plantilla no l'ha de localitzar (xhtml2pdf vol '12.5').
            cell["width"] = f'{sum(widths[cell["col_index"]:cell["col_index"] + cell["colspan"]]):.2f}'

    for cells in header:
        set_widths(cells)
    for row in body:
        set_widths(row["cells"])

    header_rows = [{"cells": cells, "kind": "columns"} for cells in header]

    # Partició per grups principals: cada grup és una taula que repeteix, a cada
    # pàgina, la capçalera de columnes i el títol del grup (així no es perd el context).
    group_starts = [i for i, r in enumerate(body) if r["css"] == "section"]
    content_rows = sum(1 for r in body if r["css"] != "spacer")
    chunks = []
    if group_starts and content_rows / len(group_starts) >= MIN_ROWS_PER_GROUP:
        if group_starts[0] > 0:
            chunks.append((None, body[:group_starts[0]]))
        for pos, start in enumerate(group_starts):
            end = group_starts[pos + 1] if pos + 1 < len(group_starts) else len(body)
            chunk = [r for r in body[start + 1:end]]
            while chunk and chunk[-1]["css"] == "spacer":
                chunk.pop()
            chunks.append((body[start], chunk))
    else:
        chunks.append((None, body))

    result = []
    for index, (group, rows) in enumerate(chunks):
        rows = [r for r in rows if not (r["css"] == "spacer" and r is rows[0])]
        head = list(header_rows)
        if group is not None:
            head.append({"cells": group["cells"], "kind": "section"})
        if not head and not rows:
            continue
        result.append({
            "captions": table["captions"] if index == 0 else [],
            "header": head,
            "repeat": len(head),
            "rows": rows,
            "row_count": len(rows),
            "column_count": column_count,
        })
    return result


# ---------------------------------------------------------------------------
# Presentació
# ---------------------------------------------------------------------------

def _font_size(column_count):
    if column_count <= 6:
        return 9
    if column_count <= 10:
        return 8
    if column_count <= 15:
        return 7
    if column_count <= 22:
        return 6
    return 5


_HEX_COLOR_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _parse_hex(value):
    """(r, g, b) d'un color '#rrggbb' o '#rgb', o None si no és vàlid (va dins del CSS)."""
    match = _HEX_COLOR_RE.match((value or "").strip())
    if not match:
        return None
    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(d * 2 for d in digits)
    return tuple(int(digits[i:i + 2], 16) for i in (0, 2, 4))


def _to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, round(c))) for c in rgb))


def _mix(rgb, other, amount):
    """Barreja `amount` (0-1) de `other` dins de `rgb`."""
    return tuple(c + (o - c) * amount for c, o in zip(rgb, other))


def _luminance(rgb):
    def channel(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


def build_palette(main_color, secondary_color):
    """Colors del PDF a partir dels dos colors de l'empresa.

    Cada instal·lació fa servir el parell a la seva manera (fons fosc + text clar o
    al revés), així que el més fosc dels dos és l'accent (capçaleres, títols) i
    l'altre, el text sobre l'accent si s'hi llegeix bé. Els fons suaus en surten.
    """
    from service.utils.contract_company import DEFAULT_MAIN_COLOR

    colors = [c for c in (_parse_hex(main_color), _parse_hex(secondary_color)) if c]
    if not colors:
        colors = [_parse_hex(DEFAULT_MAIN_COLOR)]
    accent = min(colors, key=_luminance)
    light = max(colors, key=_luminance)
    # L'accent ha de llegir-se sobre blanc (títols, text dels grups).
    while _contrast(accent, WHITE) < 4.5:
        accent = _mix(accent, BLACK, 0.15)
    on_accent = light if light != accent and _contrast(accent, light) >= 4.5 else WHITE
    return {
        "accent": _to_hex(accent),
        "accent_dark": _to_hex(_mix(accent, BLACK, 0.25)),
        "on_accent": _to_hex(on_accent),
        "section_bg": _to_hex(_mix(accent, WHITE, 0.88)),
        "total_bg": _to_hex(_mix(accent, WHITE, 0.82)),
        "total_border": _to_hex(_mix(accent, WHITE, 0.45)),
        "odd_bg": _to_hex(_mix(accent, WHITE, 0.96)),
        "filters_bg": _to_hex(_mix(accent, WHITE, 0.93)),
        "subsection_border": _to_hex(_mix(accent, WHITE, 0.55)),
    }


def get_default_company():
    """Empresa subministradora per defecte de la instal·lació."""
    from service.models import Company

    active = Company.objects.filter(is_active=True).order_by("id")
    return (
        active.filter(is_default=True).first()
        or active.filter(is_provider=True).first()
        or active.first()
    )


def _company_context():
    """Nom, logo i colors de l'empresa per defecte per a la capçalera del PDF."""
    from service.utils.contract_company import company_colors

    company = get_default_company()
    palette = build_palette(*company_colors(company))
    if company is None:
        return None, None, palette

    logo = None
    if company.logo:
        try:
            path = company.logo.path
            if os.path.exists(path):
                logo = path
        except (NotImplementedError, ValueError):
            path = None
        domain_media = getattr(settings, "DOMAIN_MEDIA", "") or ""
        if not logo and domain_media.startswith("http"):
            logo = f"{domain_media}{settings.MEDIA_URL}{company.logo.name}"
    return company.name, logo, palette


def _format_period_date(value):
    if isinstance(value, str):
        try:
            value = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value[:10]
    return format_cell_value(value)[0]


def build_report_pdf(workbook, title, filters_display=None, start_date=None, end_date=None):
    """PDF (bytes) d'un llibre openpyxl amb la plantilla genèrica d'informes."""
    from coredata.utils.template_utils import build_template_candidates
    from xhtml2pdf import pisa

    sheets = []
    total_rows = 0
    for ws in workbook.worksheets:
        if getattr(ws, "sheet_state", "visible") != "visible":
            continue
        sheet = _sheet_to_blocks(ws)
        if not sheet or not sheet["tables"]:
            continue
        total_rows += sum(t["row_count"] for t in sheet["tables"])
        if total_rows > MAX_PDF_ROWS:
            raise ReportTooLargeForPdf(
                _("L'informe té massa files per generar-ne un PDF (més de %(max)s). Descarregueu-lo en Excel.")
                % {"max": MAX_PDF_ROWS}
            )
        sheet["font_size"] = _font_size(sheet["column_count"])
        sheets.append(sheet)

    if not sheets:
        raise ReportPdfError(_("L'informe no té dades per generar-ne un PDF."))

    max_columns = max(s["column_count"] for s in sheets)
    company_name, logo, palette = _company_context()

    # Les opcions booleanes desactivades ("Inclou ...: No") no aporten res al PDF.
    filters = [
        f for f in (filters_display or [])
        if isinstance(f, dict) and f.get("label") and f.get("value") not in (None, "", [], False, "No")
    ]

    # Els filtres ja inclouen el període quan venen de la cua d'informes.
    period = None
    if start_date and end_date and not filters:
        period = f"{_format_period_date(start_date)} - {_format_period_date(end_date)}"

    html = render_to_string(
        build_template_candidates(PDF_TEMPLATE, lang=settings.LANGUAGE_CODE),
        {
            "title": title or _("Informe"),
            "period": period,
            "filters": filters,
            "sheets": sheets,
            "show_sheet_names": len(sheets) > 1,
            "landscape": max_columns > 6,
            "company_name": company_name,
            "logo": logo,
            "colors": palette,
            "generated_at": timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M"),
        },
    )

    buffer = BytesIO()
    status = pisa.CreatePDF(html, dest=buffer, encoding="utf-8")
    if status.err:
        raise ReportPdfError(_("No s'ha pogut generar el PDF de l'informe."))
    return buffer.getvalue()


def convert_report_content_to_pdf(content, filename, title, options=None, start_date=None, end_date=None):
    """Converteix el contingut d'un informe a PDF si és un Excel.

    Retorna (content, filename). Si el contingut no és un llibre Excel (p. ex.
    informes en TXT o CSV) es retorna sense canvis.
    """
    workbook = _load_workbook(content)
    if workbook is None:
        logger.info("Informe sense format Excel: no es converteix a PDF")
        return content, filename

    options = options or {}
    pdf_bytes = build_report_pdf(
        workbook,
        options.get("title") or title,
        filters_display=options.get("filters_display"),
        start_date=start_date,
        end_date=end_date,
    )
    base_name = os.path.splitext(filename)[0] if filename else "informe"
    return pdf_bytes, f"{base_name}.pdf"
