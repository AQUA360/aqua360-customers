"""Lectura dels fitxers d'intercanvi de l'ACA de 350 posicions (entrada).

Documents de l'ACA (ZIP "Estructura dels fitxers, descarregables, models i
instruccions" de la pàgina d'entitats subministradores):
- 04_estructura_fitxer_registre_ampliacio.pdf (v4.1): Ampliació de trams, aplicació "AT".
  És el mateix disseny que genera `aca_bonification_export_service`.
- 05_estructura_fitxer_registre_tarifa_social.pdf (v1.4): Tarifa social, aplicació "CS".

Tots dos tenen capçalera (10), un detall (20) per sol·licitud i total (30), i el
detall només difereix en dos camps:
- posició 288-289: AT "Nombre de persones a aplicar"; CS "Col·lectiu" (llista 5.3:
  AT, CJ, CI, NC, RM, NB, FA, LM, 90, 92). En els tancaments que envia l'ACA hi ve "TA".
- posició 329-350: AT espai lliure; CS "Informe col·lectiu" (nom del fitxer si el
  col·lectiu és 92).

Particularitats que no diuen els documents però sí els fitxers reals:
- Venen en Windows-1252/ISO-8859-1 i amb CRLF.
- El codi postal arriba sense el zero de l'esquerra ("8310").
"""
from datetime import datetime

RECORD_LENGTH = 350

HEADER_FIELDS = (
    ('record_code', 2),
    ('supplier_code', 4),
    ('supplier_nif', 20),
    ('generation_date', 8),
    ('application', 2),
)

DETAIL_FIELDS = (
    ('record_code', 2),
    ('origin', 1),
    ('request_date', 8),
    ('first_surname', 25),
    ('second_surname', 25),
    ('name', 20),
    ('document_type', 1),
    ('document_number', 20),
    ('street_type', 2),
    ('street_name', 50),
    ('street_number', 4),
    ('street_letter', 1),
    ('building', 2),
    ('stair', 2),
    ('floor', 3),
    ('door', 4),
    ('postal_code', 5),
    ('ine_code', 6),
    ('phone_1', 10),
    ('phone_2', 10),
    ('email', 100),
    ('num_persons', 2),  # CS: col·lectiu de tarifa social
    ('supplier_code', 4),
    ('policy_number', 15),
    ('authorizes_census_review', 1),
    ('aca_result', 2),
    ('censat_adreca', 1),
    ('num_persons_censats', 2),  # CS: codi intern "00"
    ('collective_report', 22),  # AT: espai lliure
)

TOTAL_FIELDS = (
    ('record_code', 2),
    ('supplier_code', 4),
    ('supplier_nif', 20),
    ('total_requests', 8),
    ('total_records', 8),
)

# Codis de tancament: llista 5.4 de l'AT (20-22) i 5.5 de la CS (20, 22, 23).
CLOSING_RESULT_CODES = ('20', '21', '22', '23')
CLOSING_NUM_PERSONS = 'TA'
# Resultat del tràmit (5.3 AT / 5.4 CS): l'únic que dona dret a la bonificació.
ACCEPTED_RESULT_CODE = '01'


class ACAExchangeFileError(ValueError):
    pass


def looks_like_exchange_file(raw):
    """Cert si el contingut (bytes) comença amb una capçalera de 350 posicions."""
    first_line = raw.lstrip(b'\xef\xbb\xbf').split(b'\n', 1)[0].rstrip(b'\r')
    return first_line[:2] == b'10' and len(first_line) == RECORD_LENGTH


def _decode(raw):
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode('cp1252', errors='replace')


def _slice(line, fields):
    values = {}
    position = 0
    for key, length in fields:
        values[key] = line[position:position + length].strip()
        position += length
    return values


def _parse_date(value):
    try:
        return datetime.strptime(value, '%Y%m%d').date()
    except (TypeError, ValueError):
        return None


def _postal_code(value):
    return value.zfill(5) if value.isdigit() else value


def _address(detail):
    number = f"{detail['street_number']}{detail['street_letter']}"
    parts = [
        detail['street_type'], detail['street_name'], number,
        detail['building'], detail['stair'], detail['floor'], detail['door'],
    ]
    return ' '.join(part for part in parts if part)


def is_closing(detail):
    return (
        detail['num_persons'].upper() == CLOSING_NUM_PERSONS
        or detail['aca_result'] in CLOSING_RESULT_CODES
    )


def parse_exchange_file(raw):
    """Retorna {'header': {...}, 'details': [...], 'total': {...}} a partir dels bytes
    del fitxer. Llança ACAExchangeFileError si l'estructura no quadra."""
    text = _decode(raw).lstrip('﻿')
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise ACAExchangeFileError('El fitxer és buit.')

    header, total, details = None, None, []
    for number, line in enumerate(lines, start=1):
        if len(line) > RECORD_LENGTH:
            raise ACAExchangeFileError(f'La línia {number} fa {len(line)} caràcters (n\'hi ha d\'haver {RECORD_LENGTH}).')
        line = line.ljust(RECORD_LENGTH)
        code = line[:2]
        if code == '10':
            header = _slice(line, HEADER_FIELDS)
        elif code == '20':
            details.append(_slice(line, DETAIL_FIELDS))
        elif code == '30':
            total = _slice(line, TOTAL_FIELDS)
        else:
            raise ACAExchangeFileError(f'La línia {number} té un codi de registre desconegut ("{code}").')

    if not header:
        raise ACAExchangeFileError('Falta el registre de capçalera (10).')
    if total:
        if total['total_requests'].isdigit() and int(total['total_requests']) != len(details):
            raise ACAExchangeFileError(
                f"El registre de total diu {int(total['total_requests'])} sol·licituds però el fitxer en té {len(details)}."
            )

    header['generation_date'] = _parse_date(header['generation_date'])
    return {'header': header, 'details': details, 'total': total}


def details_to_changes(details, application='AT'):
    """Converteix els registres de detall en dades per a `ACADocumentChange`.

    `accepted` es proposa a partir del resultat del tràmit (01 o tancament); l'usuari
    el pot canviar abans de marcar el document com a processat."""
    social = (application or '').upper() == 'CS'
    changes = []
    for detail in details:
        closing = is_closing(detail)
        full_name = ' '.join(
            part for part in (detail['first_surname'], detail['second_surname'], detail['name']) if part
        )
        changes.append({
            'person_name': full_name,
            'person_NIF': detail['document_number'],
            'address': _address(detail),
            'postal_code': _postal_code(detail['postal_code']),
            'city_code': detail['ine_code'],
            'contract_code': detail['policy_number'],
            'request_date': _parse_date(detail['request_date']),
            'num_persons': detail['num_persons'] if not social else '',
            'social_collective': detail['num_persons'] if social else '',
            'collective_report': detail['collective_report'] if social else '',
            'aca_result': detail['aca_result'],
            'closing': closing,
            'accepted': closing or detail['aca_result'] in (ACCEPTED_RESULT_CODE, ''),
        })
    return changes
