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

def get_address_extra_suffix(address):
    # L'ampliació (bar, local...) va al final i separada, sense substituir l'edifici
    address_extra = (address.address_extra or '').strip()
    return f", {address_extra}" if address_extra else ''

def get_address_complete_without_city(address):
    number_display = str(address.street_number) if address.street_number else ''
    
    floor_door = []
    if address.floor:
        floor_door.append(address.floor)
    if address.door:
        floor_door.append(address.door)
    
    return f"{str(address.street)}, {number_display if number_display else ''} {address.building if address.building else ''} {address.stair if address.stair else ''} {'-'.join(floor_door) if floor_door else ''}".strip() + get_address_extra_suffix(address)

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