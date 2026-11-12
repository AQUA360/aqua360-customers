"""
service/utils/meter_bulk_change_report.py

Genera l'informe en Excel d'una confirmació de canvi massiu de comptadors.
No depèn de models: rep les dades ja calculades pel servei.
"""
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

HEADER_FONT = Font(name="Arial", bold=True)
BODY_FONT = Font(name="Arial")
HEADER_FILL = PatternFill("solid", start_color="DDEBF7")
OK_FILL = PatternFill("solid", start_color="E2EFDA")
KO_FILL = PatternFill("solid", start_color="FCE4D6")


def _set_cell(ws, row, column, value):
    """
    Escriu el valor sempre com a dada literal. openpyxl converteix en fórmula
    qualsevol text que comenci per '=', i les dades venen del fitxer pujat
    (codis, nom del fitxer...): forcem el tipus text perquè Excel no l'avaluï.
    """
    cell = ws.cell(row=row, column=column, value=value)
    if cell.data_type == 'f':
        cell.data_type = 's'
    return cell


def _write_table(ws, headers, rows, widths):
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
    for r, row in enumerate(rows, 2):
        for c, value in enumerate(row, 1):
            _set_cell(ws, r, c, value).font = BODY_FONT
    for col, width in enumerate(widths, 1):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = width
    ws.freeze_panes = "A2"


def build_report(*, analysis, result, applied_rows, created_rows,
                 user_label, filename, executed_at):
    """Retorna els bytes d'un .xlsx amb el resum i el detall de l'operació."""
    stats = result['stats']
    failed_by_row = {e['row']: e['message'] for e in result['errors']}

    wb = Workbook()

    # --- Resum ---------------------------------------------------------------
    ws = wb.active
    ws.title = "Resum"
    summary = [
        ("Canvi de comptadors en massa", None),
        (None, None),
        ("Usuari", user_label),
        ("Data i hora", executed_at.strftime("%d/%m/%Y %H:%M:%S")),
        ("Fitxer", filename),
        (None, None),
        ("Files del fitxer", stats.get('total_rows', 0)),
        ("Canvis aplicats", stats.get('changed', 0)),
        ("Comptadors nous creats", stats.get('created', 0)),
        ("Canvis fallats en aplicar", stats.get('failed', 0)),
        ("Files amb error o no trobades", stats.get('errors', 0) + stats.get('not_found', 0)),
        ("Codis repetits al fitxer", stats.get('duplicate_codes_in_file', 0)),
    ]
    for r, (label, value) in enumerate(summary, 1):
        ws.cell(row=r, column=1, value=label).font = HEADER_FONT if (r == 1 or value is not None) else BODY_FONT
        _set_cell(ws, r, 2, value).font = BODY_FONT
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 60

    # --- Canvis --------------------------------------------------------------
    ws = wb.create_sheet("Canvis")
    rows = []
    for ch in analysis['changes']:
        applied = ch['row'] in applied_rows
        warnings = '; '.join(f"{w['code']}: {w['detail']}" for w in ch.get('warnings', []))
        detail = warnings if applied else failed_by_row.get(ch['row'], '')
        rows.append([
            ch['row'], ch['code'], ch['new_code'],
            "Sí" if ch['row'] in created_rows else "No",
            ch['supply_point']['token'], ch['supply_point']['address'],
            ch['final_reading'], ch['initial_reading'], ch['change_date'],
            "Aplicat" if applied else "Error", detail,
        ])
    _write_table(ws,
                 ["Fila", "Comptador anterior", "Comptador nou", "Nou creat",
                  "Punt de subministrament", "Adreça", "Lectura final",
                  "Lectura inicial", "Data del canvi", "Resultat", "Detall"],
                 rows, [7, 20, 20, 11, 22, 45, 14, 15, 15, 11, 50])
    for r in range(2, len(rows) + 2):
        ws.cell(row=r, column=10).fill = OK_FILL if rows[r - 2][9] == "Aplicat" else KO_FILL

    # --- Errors / no trobats / repetits (només si n'hi ha) -------------------
    if result['errors']:
        ws = wb.create_sheet("Errors")
        _write_table(ws, ["Fila", "Codi", "Missatge"],
                     [[e['row'], e['code'], e['message']] for e in result['errors']],
                     [7, 20, 100])
    if result['not_found']:
        ws = wb.create_sheet("No trobats")
        _write_table(ws, ["Codi del comptador actual"],
                     [[c] for c in result['not_found']], [30])
    if result['duplicate_codes_in_file']:
        ws = wb.create_sheet("Codis repetits")
        _write_table(ws, ["Codi repetit (no s'ha aplicat)"],
                     [[c] for c in result['duplicate_codes_in_file']], [34])

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()