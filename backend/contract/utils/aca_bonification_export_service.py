"""Generació del fitxer d'intercanvi "Ampliació de trams" per a l'ACA.

Estructura definida al document "04_estructura_fitxer_registre_ampliacio.pdf"
(Agència Catalana de l'Aigua, v4.1): registre de capçalera (10), un registre de
detall (20) per sol·licitud, i un registre de total (30). Longitud de línia: 350.

El document no especifica cap requisit de retorn de carro (CRLF): els salts de
línia són només '\\n', ja que un CRLF fa que cada registre s'interpreti amb 351
caràcters (el '\\r' final) si qui llegeix el fitxer separa únicament per '\\n'.
"""
from datetime import datetime

RECORD_LENGTH = 350


def x(value, length):
    """Camp alfanumèric: ajustat a l'esquerra, espais a la dreta, retallat a `length`."""
    value = '' if value is None else str(value)
    return value[:length].ljust(length)


def n(value, length):
    """Camp numèric: ajustat a la dreta, zeros a l'esquerra."""
    value = '' if value is None else str(value)
    digits = ''.join(ch for ch in value if ch.isdigit())
    return digits[-length:].rjust(length, '0')


def _document_type_code(person):
    identification_type = getattr(person, 'identification_type', None)
    label = ((identification_type.token or identification_type.name) if identification_type else '') or ''
    label = label.upper()
    if 'NIE' in label:
        return '2'
    if 'PASS' in label:
        return '3'
    return '1'


def _street_type_code(address):
    """Codi de la llista de valors 5.2 (Tipus de via). Només es fa servir
    `aca_abbreviation` (l'abreviatura interna, p.ex. "C" per Carrer, NO és un
    codi ACA vàlid): si no està informada correctament es retorna "VP" (Via
    Pública Indeterminada), en lloc d'un codi inventat."""
    street = getattr(address, 'street', None)
    street_type = getattr(street, 'type', None)
    if not street_type or not street_type.aca_abbreviation:
        return 'VP'
    return street_type.aca_abbreviation


def _supply_address(contract):
    """L'adreça a declarar és la del punt de subministrament (SupplyPoint),
    no la de contacte/facturació del titular (poden ser adreces diferents)."""
    if not contract:
        return None
    supply_point = contract.supply_point_default
    if supply_point and supply_point.address:
        return supply_point.address
    if contract.address_contact and contract.address_contact.address:
        return contract.address_contact.address
    return None


def build_header_record(supplier_code, supplier_nif, generation_date=None):
    generation_date = generation_date or datetime.now().date()
    return (
        x('10', 2)
        + n(supplier_code, 4)
        + x(supplier_nif, 20)
        + x(generation_date.strftime('%Y%m%d'), 8)
        + x('AT', 2)
        + x('', 314)
    )


def build_detail_record(aca_request, supplier_code, ine_code):
    bonification = aca_request.bonification
    contract = bonification.contract
    person = bonification.person or (contract.holder if contract else None)
    address = _supply_address(contract)
    street_number = getattr(address, 'street_number', None)

    surname = (person.surname or '').strip().split(' ', 1) if person else ['']
    first_surname = surname[0] if surname else ''
    second_surname = surname[1] if len(surname) > 1 else ''

    phones = []
    email = ''
    if contract:
        if contract.person_contact_email and contract.person_contact_email.email:
            email = contract.person_contact_email.email
        for contact in contract.contacts.all():
            if contact.phone and contact.phone not in phones:
                phones.append(contact.phone)
            if not email and contact.email:
                email = contact.email
    phone_1 = phones[0] if len(phones) > 0 else ''
    phone_2 = phones[1] if len(phones) > 1 else ''

    policy_number = (contract.token or '').replace('/', '') if contract else ''

    return (
        x('20', 2)
        + x('E', 1)
        + x((bonification.requested_at or datetime.now()).strftime('%Y%m%d'), 8)
        + x(first_surname, 25)
        + x(second_surname, 25)
        + x(person.name if person else '', 20)
        + x(_document_type_code(person) if person else '1', 1)
        + x(person.token if person else '', 20)
        + x(_street_type_code(address), 2)
        + x(getattr(getattr(address, 'street', None), 'name', None), 50)
        + x(street_number.number if street_number else '', 4)
        + x(street_number.number_suffix if street_number else '', 1)
        + x(getattr(address, 'building', None), 2)
        + x(getattr(address, 'stair', None), 2)
        + x(getattr(address, 'floor', None), 3)
        + x(getattr(address, 'door', None), 4)
        + x(getattr(address, 'postal_code', None), 5)
        + n(ine_code, 6)
        + x(phone_1, 10)
        + x(phone_2, 10)
        + x(email, 100)
        + n(aca_request.num_persons_to_apply, 2)
        + n(supplier_code, 4)
        + x(policy_number, 15)
        + x('S' if aca_request.authorizes_census_review else 'N', 1)
        + x(aca_request.aca_result or '', 2)
        + x(aca_request.censat_adreca or '', 1)
        + n(aca_request.num_persons_censats, 2)
        + x('', 22)
    )


def build_total_record(supplier_code, supplier_nif, total_requests, total_records):
    return (
        x('30', 2)
        + n(supplier_code, 4)
        + x(supplier_nif, 20)
        + n(total_requests, 8)
        + n(total_records, 8)
        + x('', 308)
    )


def build_ampliacio_trams_file(pending_requests, supplier_code, supplier_nif, ine_code, generation_date=None):
    """Retorna el contingut (str) del fitxer d'intercanvi per als ACABonificationRequest donats."""
    detail_lines = [build_detail_record(req, supplier_code, ine_code) for req in pending_requests]
    total_records = len(detail_lines) + 2  # capçalera + total

    lines = [build_header_record(supplier_code, supplier_nif, generation_date)]
    lines.extend(detail_lines)
    lines.append(build_total_record(supplier_code, supplier_nif, len(detail_lines), total_records))

    for line in lines:
        assert len(line) == RECORD_LENGTH, f"Registre amb longitud incorrecta: {len(line)}"

    return '\n'.join(lines) + '\n'
