"""Lectura i validació d'un fitxer FACTDETA en baixa (format 2026), independent del codi que el genera.

Les posicions surten del document 03 de l'ACA "Estructura del fitxer. Declaració de la facturació
detallada en baixa" i les comprovacions, del document 08 "ValidacionsFactDeta_2026" (actualització
22/10/2026) i del validador de l'ACA del 02/11/2026. Serveix per desglossar els totals d'un fitxer (també d'altres
programes) i comparar-los amb els informes de facturació abans de passar-lo pel validador de l'ACA.
"""
import datetime
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation

import openpyxl
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font

LINE_LENGTH = 664
ZERO = Decimal('0')
INCIDENCE = 'Incidència'
WARNING = 'Avís'
TARIFF_TYPES = {
    'D': 'Domèstica', 'I': 'Industrial', 'Q': 'Quota', 'M': 'Mesurament directe', 'A': 'Usos municipals',
    'E': 'Prestació gratuïta / horts públics', 'G': 'Agrícoles', 'X': 'Extinció incendis',
}
CONSUMPTION_ONLY = ('E', 'G', 'X', 'M')
PART_FIXA_START_DATE = datetime.date(2026, 1, 1)
FILE_NAME_RE = re.compile(r'^FD(\d{4})_(\d{6})_(\d{4})\.txt$', re.IGNORECASE)


def X(length):
    return ('X', length, 0)


def N(int_digits, dec_digits=0):
    return ('9', int_digits + dec_digits, dec_digits)


def D():
    return ('D', 8, 0)


HEADER_FIELDS = [
    ('record', "Codi de registre", X(2)),
    ('entity', "Codi de l'entitat subministradora", N(4)),
    ('nif', "NIF/CIF de l'entitat subministradora", X(12)),
    ('application', "Aplicació", X(8)),
    ('year', "Any de facturació", N(4)),
    ('ine', "Codi de municipi", N(6)),
    ('free', "Espai lliure", X(628)),
]

DETAIL_FIELDS = [
    ('record', "Codi de registre", X(2)),
    ('ine', "Codi de municipi", N(6)),
    ('invoice', "Número de factura", X(10)),
    ('issue_date', "Data d'emissió", D()),
    ('customer', "Identificació de l'abonat", X(20)),
    ('tariff', "Tipus de tarifa", X(1)),
    ('surname1', "Primer cognom", X(15)),
    ('surname2', "Segon cognom", X(15)),
    ('name', "Nom", X(10)),
    ('street_code', "Codi via", X(2)),
    ('street', "Nom via", X(50)),
    ('street_number', "Número", X(7)),
    ('floor', "Pis", X(2)),
    ('door', "Porta", X(2)),
    ('stair', "Escala", X(2)),
    ('postal_code', "CP", X(5)),
    ('city', "Població", X(25)),
    ('policy', "Número de pòlissa", X(15)),
    ('meter', "Comptador", X(25)),
    ('billing_system', "Sistema de facturació", X(1)),
    ('period_start', "Data inici període", D()),
    ('period_end', "Data fi període", D()),
    ('consumed_volume', "Volum consumit total", N(12)),
    ('billed_volume', "Volum facturat total", N(12)),
    *[
        field
        for tram in range(1, 5)
        for field in (
            (f't{tram}_volume', f"Volum {tram}r tram", N(9)),
            (f't{tram}_rate', f"Tarifa {tram}r tram", N(3, 6)),
            (f't{tram}_amount', f"Import {tram}r tram", N(12, 4)),
        )
    ],
    ('social_volume', "Volum bo social", N(5)),
    ('social_rate', "Tarifa bo social", N(3, 6)),
    ('social_amount', "Import bo social", N(8, 4)),
    ('general_volume', "Volum tarifa general ind.", N(12)),
    ('general_rate', "Tarifa general ind.", N(3, 6)),
    ('general_amount', "Import tarifa general ind.", N(12, 4)),
    ('specific_volume', "Volum tarifa específica ind.", N(12)),
    ('specific_rate', "Tarifa específica ind.", N(3, 6)),
    ('specific_amount', "Import tarifa específica ind.", N(12, 4)),
    ('leak_volume', "Volum fuites", N(9)),
    ('leak_rate', "Tarifa fuites", N(3, 6)),
    ('leak_amount', "Import fuites", N(12, 4)),
    ('quota_annual', "Import quota anual", N(12, 4)),
    ('quota_billed', "Import facturat quota", N(12, 4)),
    ('variable_amount', "Import part variable i quota ramadera", N(12, 2)),
    ('fixed_amount', "Import part fixa", N(11, 2)),
    ('total_amount', "Import total cànon", N(12, 2)),
    ('cancelled_invoice', "Número factura anul·lada", X(10)),
    ('cancelled_date', "Data factura anul·lada", D()),
    ('alternative_network', "Xarxes alternatives", X(1)),
    ('tram_extension', "Ampliació de trams", X(1)),
    ('inhabitants', "Nombre d'habitants", N(2)),
    ('social_tariff', "Bo social", X(1)),
    ('vulnerable', "Vulnerable", X(1)),
    ('establishment', "Codi establiment", X(10)),
    ('homes', "Nombre d'habitatges", N(3)),
    ('places', "Nombre de places", N(4)),
    ('utm_x', "Coordenada X UTM", N(6, 2)),
    ('utm_y', "Coordenada Y UTM", N(7, 2)),
]

TOTAL_FIELDS = [
    ('record', "Codi de registre", X(2)),
    ('entity', "Codi de l'entitat subministradora", N(4)),
    ('nif', "NIF/CIF de l'entitat subministradora", X(12)),
    ('ine', "Codi de municipi", N(6)),
    ('invoices', "Nombre total de factures", N(8)),
    ('records', "Nombre total de registres", N(8)),
    ('free', "Espai lliure", X(624)),
]

# (volum, tarifa, import) de cada concepte amb tarifa
CONCEPTS = [
    *[(f"{tram}r tram", f't{tram}_volume', f't{tram}_rate', f't{tram}_amount') for tram in range(1, 5)],
    ("Bo social", 'social_volume', 'social_rate', 'social_amount'),
    ("Tarifa general ind.", 'general_volume', 'general_rate', 'general_amount'),
    ("Tarifa específica ind.", 'specific_volume', 'specific_rate', 'specific_amount'),
    ("Fuites", 'leak_volume', 'leak_rate', 'leak_amount'),
]
DOMESTIC_KEYS = [key for name, *keys in CONCEPTS[:5] for key in keys]
INDUSTRIAL_KEYS = [key for name, *keys in CONCEPTS[5:7] for key in keys]
LEAK_KEYS = list(CONCEPTS[7][1:])
QUOTA_KEYS = ['quota_annual', 'quota_billed']
VOLUME_RATE_AMOUNT_KEYS = ['billed_volume'] + [key for name, *keys in CONCEPTS for key in keys] + QUOTA_KEYS + [
    'variable_amount', 'fixed_amount', 'total_amount',
]
SUMMED_KEYS = ['consumed_volume', 'billed_volume'] + [
    key for name, volume, rate, amount in CONCEPTS for key in (volume, amount)
] + QUOTA_KEYS + ['variable_amount', 'fixed_amount', 'total_amount']
LABELS = {key: label for key, label, _fmt in DETAIL_FIELDS}

for _fields in (HEADER_FIELDS, DETAIL_FIELDS, TOTAL_FIELDS):
    assert sum(fmt[1] for _key, _label, fmt in _fields) == LINE_LENGTH


class FieldError(ValueError):
    pass


def _parse_number(text, dec_digits):
    """9(n)v9(d): sense punt decimal i amb el signe negatiu, si n'hi ha, al primer dígit."""
    sign = 1
    digits = text
    if text.startswith('-'):
        sign, digits = -1, text[1:]
    if not digits.isdecimal():
        raise FieldError(f"valor numèric no vàlid «{text}»")
    return sign * Decimal(digits).scaleb(-dec_digits)


def _parse_date(text):
    if not text.strip():
        return None
    try:
        return datetime.datetime.strptime(text, '%Y%m%d').date()
    except ValueError:
        raise FieldError(f"data no vàlida «{text}»")


def parse_line(line, fields):
    """Retorna (valors, errors de format)."""
    values, errors, position = {}, [], 0
    for key, label, (kind, length, dec_digits) in fields:
        text = line[position:position + length]
        position += length
        try:
            if kind == '9':
                values[key] = _parse_number(text, dec_digits)
            elif kind == 'D':
                values[key] = _parse_date(text)
            else:
                values[key] = text.rstrip()
        except FieldError as e:
            values[key] = None
            errors.append(f"{label}: {e}")
    return values, errors


class FactdetaFile:
    def __init__(self, file_name=None):
        self.file_name = file_name
        self.header = None
        self.total = None
        self.records = []
        self.issues = []

    def add_issue(self, level, line_number, message, invoice=''):
        self.issues.append({'level': level, 'line': line_number, 'invoice': invoice, 'message': message})

    @property
    def incidences(self):
        return [issue for issue in self.issues if issue['level'] == INCIDENCE]


def read_factdeta(content, file_name=None):
    """Llegeix i valida un fitxer FACTDETA. `content` pot ser bytes o text."""
    if isinstance(content, bytes):
        try:
            content = content.decode('utf-8')
        except UnicodeDecodeError:
            content = content.decode('latin-1')
    factdeta = FactdetaFile(file_name)
    lines = [line.rstrip('\r') for line in content.split('\n')]
    while lines and not lines[-1]:
        lines.pop()

    for number, line in enumerate(lines, start=1):
        if len(line) != LINE_LENGTH:
            factdeta.add_issue(INCIDENCE, number, f"la línia té {len(line)} caràcters en lloc de {LINE_LENGTH}")
        record_type = line[:2]
        if record_type == '10':
            if number != 1:
                factdeta.add_issue(INCIDENCE, number, "registre de capçalera fora de la primera línia")
            factdeta.header, errors = parse_line(line, HEADER_FIELDS)
        elif record_type == '30':
            if number != len(lines):
                factdeta.add_issue(INCIDENCE, number, "registre de total fora de l'última línia")
            factdeta.total, errors = parse_line(line, TOTAL_FIELDS)
        elif record_type == '20':
            record, errors = parse_line(line, DETAIL_FIELDS)
            record['line'] = number
            factdeta.records.append(record)
        else:
            factdeta.add_issue(INCIDENCE, number, f"tipus de registre desconegut «{record_type}»")
            continue
        invoice = line[8:18].strip() if record_type == '20' else ''
        for error in errors:
            factdeta.add_issue(INCIDENCE, number, error, invoice)

    _validate_file(factdeta, len(lines))
    for record in factdeta.records:
        for level, message in validate_record(record, factdeta.header):
            factdeta.add_issue(level, record['line'], message, record.get('invoice') or '')
    return factdeta


def _validate_file(factdeta, line_count):
    header, total = factdeta.header, factdeta.total
    if not header:
        factdeta.add_issue(INCIDENCE, 1, "falta el registre de capçalera (10)")
    elif header.get('application') != 'FACTDETA':
        factdeta.add_issue(INCIDENCE, 1, f"l'aplicació de la capçalera és «{header.get('application')}» en lloc de FACTDETA")
    if not total:
        factdeta.add_issue(INCIDENCE, line_count, "falta el registre de total (30)")
    if header and total:
        for key, label in (('entity', "codi d'entitat"), ('nif', "NIF de l'entitat"), ('ine', "codi de municipi")):
            if header.get(key) != total.get(key):
                factdeta.add_issue(INCIDENCE, line_count, f"el {label} del total no coincideix amb la capçalera")
    if total:
        if total.get('invoices') != len(factdeta.records):
            factdeta.add_issue(INCIDENCE, line_count, f"el total declara {total.get('invoices')} factures i n'hi ha {len(factdeta.records)}")
        if total.get('records') != line_count:
            factdeta.add_issue(INCIDENCE, line_count, f"el total declara {total.get('records')} registres i n'hi ha {line_count}")
    match = FILE_NAME_RE.match(factdeta.file_name or '')
    if factdeta.file_name and not match:
        factdeta.add_issue(WARNING, 0, f"el nom del fitxer «{factdeta.file_name}» no segueix el format FDCCCC_MMMMMM_AAAA.txt")
    elif match and header:
        expected = (header.get('entity'), header.get('ine'), header.get('year'))
        if tuple(Decimal(part) for part in match.groups()) != expected:
            factdeta.add_issue(INCIDENCE, 0, "l'entitat, el municipi o l'any del nom del fitxer no coincideixen amb la capçalera")

    seen = {}
    for record in factdeta.records:
        invoice = record.get('invoice')
        if invoice in seen:
            factdeta.add_issue(INCIDENCE, record['line'], f"factura repetida (també a la línia {seen[invoice]})", invoice)
        else:
            seen[invoice] = record['line']
        if header and record.get('ine') is not None and record.get('ine') != header.get('ine'):
            factdeta.add_issue(INCIDENCE, record['line'], "el codi de municipi no coincideix amb la capçalera", invoice)


def _value(record, key):
    value = record.get(key)
    return value if isinstance(value, Decimal) else ZERO


def _within_5_percent(amount, expected):
    return abs(amount - expected) <= abs(expected) * Decimal('0.05')


def validate_record(record, header=None):
    """Comprovacions del document 08 sobre un registre de detall: [(nivell, missatge)]."""
    issues = []
    tariff = record.get('tariff')
    value = lambda key: _value(record, key)

    if tariff not in TARIFF_TYPES:
        issues.append((INCIDENCE, f"tipus de tarifa no vàlid «{tariff}»"))
    if not record.get('invoice'):
        issues.append((INCIDENCE, "sense número de factura"))
    if not record.get('policy'):
        issues.append((INCIDENCE, "sense número de pòlissa"))
    if not record.get('city'):
        issues.append((WARNING, "sense població"))
    issue_date = record.get('issue_date')
    if not issue_date:
        issues.append((INCIDENCE, "sense data d'emissió"))
    elif header and isinstance(header.get('year'), Decimal) and issue_date.year != header['year']:
        issues.append((INCIDENCE, "la data d'emissió no és de l'any de facturació del fitxer"))
    start, end = record.get('period_start'), record.get('period_end')
    if start and end and end < start:
        issues.append((INCIDENCE, "la data final del període de consum és anterior a la inicial"))

    # Conceptes que han de ser zero segons el tipus de tarifa
    zero_keys = {
        'D': INDUSTRIAL_KEYS + QUOTA_KEYS,
        'I': DOMESTIC_KEYS + QUOTA_KEYS,
        'Q': INDUSTRIAL_KEYS + LEAK_KEYS + DOMESTIC_KEYS,
        'A': DOMESTIC_KEYS + LEAK_KEYS + ['specific_volume', 'specific_rate', 'specific_amount'] + QUOTA_KEYS,
    }.get(tariff, VOLUME_RATE_AMOUNT_KEYS if tariff in CONSUMPTION_ONLY else [])
    informed = [LABELS[key] for key in zero_keys if value(key)]
    if informed:
        issues.append((INCIDENCE, f"tarifa {tariff} amb camps que han de ser zero: {', '.join(informed[:4])}"
                       + ('...' if len(informed) > 4 else '')))

    consumed, billed = value('consumed_volume'), value('billed_volume')
    if tariff in ('D', 'I', 'A'):
        if consumed * billed < 0:
            issues.append((INCIDENCE, "el volum consumit i el facturat tenen signes diferents"))
        elif abs(billed) < abs(consumed):
            issues.append((WARNING, "el volum facturat és inferior al consumit"))
        if not value('fixed_amount') and end and end >= PART_FIXA_START_DATE:
            issues.append((WARNING, "sense import de part fixa"))
    if tariff == 'D':
        declared = sum(value(f't{tram}_volume') for tram in range(1, 5)) + value('social_volume') + value('leak_volume')
        if declared != billed:
            issues.append((INCIDENCE, "la suma de trams, bo social i fuites no coincideix amb el volum facturat"))
    if tariff == 'I' and value('general_volume') + value('specific_volume') + value('leak_volume') == 0:
        issues.append((WARNING, "tarifa industrial sense volum general, específic ni de fuites"))

    for name, volume_key, rate_key, amount_key in CONCEPTS:
        volume, rate, amount = value(volume_key), value(rate_key), value(amount_key)
        if (volume or amount) and not _within_5_percent(amount, rate * volume):
            issues.append((INCIDENCE, f"{name}: l'import no és tarifa × volum (±5%)"))
    if value('leak_volume') and not value('leak_rate'):
        issues.append((INCIDENCE, "volum de fuites sense tarifa"))
    if not value('leak_volume') and value('leak_rate'):
        issues.append((INCIDENCE, "tarifa de fuites sense volum"))

    variable, fixed, total = value('variable_amount'), value('fixed_amount'), value('total_amount')
    if variable + fixed != total:
        issues.append((INCIDENCE, "l'import total no és la part variable més la fixa"))
    amounts = sum(value(amount_key) for _name, _volume, _rate, amount_key in CONCEPTS) + value('quota_billed') + fixed
    if (total or amounts) and not _within_5_percent(total, amounts):
        issues.append((INCIDENCE, "l'import total no coincideix amb la suma dels imports dels conceptes (±5%)"))

    cancelled_invoice, cancelled_date = record.get('cancelled_invoice'), record.get('cancelled_date')
    if total < 0 and not (cancelled_invoice and cancelled_date):
        issues.append((INCIDENCE, "import negatiu sense factura anul·lada"))
    if bool(cancelled_invoice) != bool(cancelled_date):
        issues.append((INCIDENCE, "cal informar alhora el número i la data de la factura anul·lada"))
    if cancelled_date and issue_date and cancelled_date > issue_date:
        issues.append((INCIDENCE, "la factura anul·lada és posterior a la factura"))
    if cancelled_invoice and cancelled_date and total > 0:
        issues.append((WARNING, "factura anul·lada informada amb imports positius"))

    if record.get('tram_extension') not in (('S', 'N') if tariff == 'D' else ('',)):
        issues.append((INCIDENCE, "ampliació de trams: «S» o «N» en tarifa domèstica, en blanc a la resta"))
    if record.get('social_tariff') not in (('S', 'N') if tariff == 'D' else ('',)):
        issues.append((INCIDENCE, "bo social: «S» o «N» en tarifa domèstica, en blanc a la resta"))
    if record.get('vulnerable') not in ('S', 'N'):
        issues.append((INCIDENCE, "vulnerable ha de ser «S» o «N»"))
    if record.get('establishment') and tariff not in ('M', 'Q'):
        issues.append((INCIDENCE, "codi d'establiment informat amb una tarifa que no és M ni Q"))
    if tariff == 'M' and not record.get('establishment'):
        issues.append((WARNING, "mesurament directe sense codi d'establiment"))
    if record.get('alternative_network') == 'R' and tariff != 'D':
        issues.append((INCIDENCE, "xarxa alternativa «R» amb una tarifa que no és domèstica"))
    if not value('utm_x') or not value('utm_y'):
        issues.append((WARNING, "sense coordenades UTM"))
    return issues


def _empty_totals():
    totals = {key: ZERO for key in SUMMED_KEYS}
    totals['count'] = 0
    return totals


def _add(totals, record):
    totals['count'] += 1
    for key in SUMMED_KEYS:
        totals[key] += _value(record, key)


def summarize_factdeta(factdeta):
    """Totals del fitxer: general, per tipus de tarifa, factures/abonaments i mes d'emissió."""
    summary = {
        'total': _empty_totals(),
        'by_tariff': defaultdict(_empty_totals),
        'by_sign': defaultdict(_empty_totals),
        'by_month': defaultdict(_empty_totals),
    }
    for record in factdeta.records:
        _add(summary['total'], record)
        _add(summary['by_tariff'][record.get('tariff') or '?'], record)
        _add(summary['by_sign']['Abonaments (total negatiu)' if _value(record, 'total_amount') < 0 else 'Factures'], record)
        issue_date = record.get('issue_date')
        _add(summary['by_month'][issue_date.strftime('%Y-%m') if issue_date else '?'], record)
    return summary


def _number(value):
    return float(value) if isinstance(value, Decimal) else value


def _code(value, length):
    """Codis numèrics (INE, entitat) amb els zeros a l'esquerra."""
    return str(int(value)).zfill(length) if isinstance(value, Decimal) else value


def _cell_value(record, key):
    return _code(record.get(key), 6) if key == 'ine' else _number(record.get(key))


def _safe_cell(sheet, value, bold=False):
    """Els valors venen del fitxer analitzat: openpyxl desaria com a fórmula qualsevol text que
    comenci per '=', i es forcen com a text."""
    is_formula_like = isinstance(value, str) and value.startswith('=')
    if not bold and not is_formula_like:
        return value
    cell = WriteOnlyCell(sheet, value=value)
    if is_formula_like:
        cell.data_type = 's'
    if bold:
        cell.font = Font(bold=True)
    return cell


def _append(sheet, values, bold=False):
    sheet.append([_safe_cell(sheet, value, bold) for value in values])


def _bold_row(sheet, values):
    _append(sheet, values, bold=True)


SUMMARY_COLUMNS = [
    ('count', "Registres"), ('consumed_volume', "Volum consumit"), ('billed_volume', "Volum facturat"),
    ('variable_amount', "Part variable"), ('fixed_amount', "Part fixa"), ('total_amount', "Total cànon"),
]


def _summary_table(sheet, title, groups, first_column):
    _bold_row(sheet, [title])
    _bold_row(sheet, [first_column] + [label for _key, label in SUMMARY_COLUMNS])
    for name, totals in groups:
        _append(sheet, [name] + [_number(totals[key]) for key, _label in SUMMARY_COLUMNS])
    _append(sheet, [])


def build_factdeta_workbook(factdeta):
    """Excel amb el resum de totals, el detall de cada registre i les validacions."""
    workbook = openpyxl.Workbook(write_only=True)
    summary = summarize_factdeta(factdeta)
    header = factdeta.header or {}

    sheet = workbook.create_sheet("Resum")
    sheet.column_dimensions['A'].width = 38
    _bold_row(sheet, ["Anàlisi del fitxer FACTDETA"])
    _append(sheet, ["Fitxer", factdeta.file_name or ''])
    _append(sheet, ["Codi entitat", _code(header.get('entity'), 4)])
    _append(sheet, ["NIF entitat", header.get('nif')])
    _append(sheet, ["Any de facturació", _number(header.get('year'))])
    _append(sheet, ["Codi INE", _code(header.get('ine'), 6)])
    _append(sheet, ["Registres de detall", len(factdeta.records)])
    _append(sheet, ["Incidències", len(factdeta.incidences)])
    _append(sheet, ["Avisos", len(factdeta.issues) - len(factdeta.incidences)])
    _append(sheet, [])

    total = summary['total']
    _bold_row(sheet, ["Totals del fitxer", "Volum", "Import"])
    _append(sheet, ["Volum consumit total", _number(total['consumed_volume'])])
    _append(sheet, ["Volum facturat total", _number(total['billed_volume'])])
    for name, volume_key, _rate_key, amount_key in CONCEPTS:
        _append(sheet, [name, _number(total[volume_key]), _number(total[amount_key])])
    _append(sheet, ["Quota anual", None, _number(total['quota_annual'])])
    _append(sheet, ["Quota facturada", None, _number(total['quota_billed'])])
    _bold_row(sheet, ["Import part variable i quota ramadera", None, _number(total['variable_amount'])])
    _bold_row(sheet, ["Import part fixa", None, _number(total['fixed_amount'])])
    _bold_row(sheet, ["Import total cànon", None, _number(total['total_amount'])])
    _append(sheet, [])

    _summary_table(sheet, "Per tipus de tarifa", [
        (f"{tariff} - {TARIFF_TYPES.get(tariff, 'desconegut')}", totals)
        for tariff, totals in sorted(summary['by_tariff'].items())
    ], "Tipus de tarifa")
    _summary_table(sheet, "Factures i abonaments", sorted(summary['by_sign'].items()), "Signe")
    _summary_table(sheet, "Per mes d'emissió", sorted(summary['by_month'].items()), "Mes")

    issues_by_message = defaultdict(int)
    for issue in factdeta.issues:
        issues_by_message[(issue['level'], issue['message'])] += 1
    _bold_row(sheet, ["Validacions", "Nivell", "Registres"])
    for (level, message), count in sorted(issues_by_message.items()):
        _append(sheet, [message, level, count])

    sheet = workbook.create_sheet("Registres")
    _bold_row(sheet, ["Línia"] + [label for _key, label, _fmt in DETAIL_FIELDS])
    for record in factdeta.records:
        _append(sheet, [record['line']] + [_cell_value(record, key) for key, _label, _fmt in DETAIL_FIELDS])

    sheet = workbook.create_sheet("Validacions")
    _bold_row(sheet, ["Línia", "Factura", "Nivell", "Validació"])
    for issue in sorted(factdeta.issues, key=lambda issue: (issue['line'], issue['level'])):
        _append(sheet, [issue['line'], issue['invoice'], issue['level'], issue['message']])
    return workbook
