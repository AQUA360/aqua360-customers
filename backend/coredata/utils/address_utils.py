#
#
#
import re

from django.db.models import Q


def normalize_address_extra(value):
    return (value or '').strip() or None

def address_extra_filter(address_extra):
    # Les adreces existents poden tenir l'ampliació a NULL, buida o amb espais als extrems
    if address_extra:
        return Q(address_extra__regex=rf'^\s*{re.escape(address_extra)}\s*$')
    return Q(address_extra__isnull=True) | Q(address_extra__regex=r'^\s*$')

def get_address_extra(address):
    return normalize_address_extra(address.address_extra) if address else None

def get_address_extra_suffix(address):
    # L'ampliació (bar, local...) va al final i separada, sense substituir l'edifici
    address_extra = get_address_extra(address)
    return f", {address_extra}" if address_extra else ''

def get_address_complete_without_city(address, include_extra=True):
    number_display = str(address.street_number) if address.street_number else ''
    
    floor_door = []
    if address.floor:
        floor_door.append(address.floor)
    if address.door:
        floor_door.append(address.door)
    
    return f"{str(address.street)}, {number_display if number_display else ''} {address.building if address.building else ''} {address.stair if address.stair else ''} {'-'.join(floor_door) if floor_door else ''}".strip() + (get_address_extra_suffix(address) if include_extra else '')

def get_address_complete_with_city(address):
    number_display = str(address.street_number) if address.street_number else ''
    
    floor_door = []
    if address.floor:
        floor_door.append(address.floor)
    if address.door:
        floor_door.append(address.door)
    
    address_extra_suffix = get_address_extra_suffix(address)

    #check if country is Spain or if Address is from SupplyPoint class
    if (address.country and address.country.iso_code == 'ES'):
        address_line = f"{str(address.street)}, {number_display if number_display else ''} {address.building if address.building else ''} {address.stair if address.stair else ''} {'-'.join(floor_door if floor_door else [''])}"
        if address_extra_suffix:
            address_line = address_line.rstrip() + address_extra_suffix
        return f"{address_line}, {address.city}".strip()
    else:
        if address.postal_code:
            postal_code = address.postal_code
        else:
            postal_code = ''
        if address.city:
            city = address.city.name
        else:
            city = ''
        if address.country:
            country = address.country.name
        else:
            country = ''
            
        address_line = f"{address.street}{', ' + str(number_display) if number_display else ''} {address.stair if address.stair else ''} {'-'.join(floor_door)}"
        if address_extra_suffix:
            address_line = address_line.rstrip() + address_extra_suffix
        return f"{address_line} - {postal_code} - {city} - {country}".strip()


def get_address_destination(address):
    if not address:
        return None

    parts = []
    if address.building:
        parts.append(str(address.building).strip())
    if address.stair:
        parts.append(str(address.stair).strip())

    floor_door = []
    if address.floor:
        floor_door.append(str(address.floor).strip())
    if address.door:
        floor_door.append(str(address.door).strip())
    if floor_door:
        parts.append('-'.join(floor_door))

    result = ' '.join(parts).strip()
    return result or None

STREET_NUMBER_FIELDS = ('number', 'number_end', 'number_suffix', 'number_end_suffix')
_STREET_NUMBER_INT_FIELDS = ('number', 'number_end')


def _clean_street_number_value(field, value):
    if value is None or (isinstance(value, str) and value.strip() == ''):
        return None
    if field in _STREET_NUMBER_INT_FIELDS:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return str(value).strip()


def resolve_street_number(street, number_type, data=None, street_number_id=None):
    """Retorna el número de carrer que correspon a les dades rebudes sense modificar-ne cap d'existent.

    Els números (`StreetNumber`) es comparteixen entre adreces de punts, persones, finques,
    comptadors i bateries: editar-ne un canviaria l'adreça de tots. Si `street_number_id`
    ja correspon a aquestes dades es reaprofita; si no, se'n busca un d'igual o se'n crea un.
    Els camps que no arriben a `data` es mantenen com els del número de `street_number_id`.
    """
    from coredata.models import StreetNumber

    data = data or {}
    current = StreetNumber.objects.filter(id=street_number_id).first() if street_number_id else None
    if street is None:
        street = current.street if current else None
    if number_type is None and current:
        number_type = current.number_type

    values = {}
    for field in STREET_NUMBER_FIELDS:
        raw = data.get(field) if field in data else (getattr(current, field) if current else None)
        values[field] = _clean_street_number_value(field, raw)

    if current and current.street_id == street.id and current.number_type_id == (number_type.id if number_type else None) \
            and all(_clean_street_number_value(f, getattr(current, f)) == values[f] for f in STREET_NUMBER_FIELDS):
        return current

    filters = Q(street=street, number_type=number_type)
    for field, value in values.items():
        if value is None:
            filters &= Q(**{f'{field}__isnull': True}) | (Q(**{field: ''}) if field not in _STREET_NUMBER_INT_FIELDS else Q(pk__in=[]))
        else:
            filters &= Q(**{field: value})
    existing = StreetNumber.objects.filter(filters).order_by('id').first()
    if existing:
        return existing
    return StreetNumber.objects.create(street=street, number_type=number_type, **values)
