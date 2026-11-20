"""Dades de les factures i pressupostos d'una sol·licitud d'escomesa.

La persona d'una sol·licitud pot no tenir encara cap contracte ni adreça de
contacte: l'adreça de la factura es busca només a la mateixa sol·licitud i a la
persona, mai a contractes o punts d'altres llocs.
"""
from coredata.utils.address_utils import get_address_complete_without_city


def _connection_request_location(connection_request):
    """Adreça de l'escomesa (carrer i número de la sol·licitud), o None."""
    if not connection_request.address_street:
        return None
    number = str(connection_request.address_street_number) if connection_request.address_street_number else ''
    floor_door = '-'.join(filter(None, [connection_request.address_floor, connection_request.address_door]))
    extra = ' '.join(filter(None, [connection_request.address_building, connection_request.address_stair, floor_door]))
    street = f"{connection_request.address_street}, {number}".strip().rstrip(',')
    city = connection_request.address_city
    province = city.province if city else None
    country = province.country if province else None
    return {
        'address': ' '.join(filter(None, [street, extra])),
        'postal_code': connection_request.address_postal_code.code if connection_request.address_postal_code else None,
        'city': city.name if city else None,
        'province': province.name if province else None,
        'country': country.name if country else None,
        'country_iso': country.iso_code if country else None,
    }


def get_address_fields(address):
    return {
        'address': get_address_complete_without_city(address),
        'postal_code': address.postal_code,
        'city': address.city.name if address.city else None,
        'province': address.province.name if address.province else None,
        'country': address.country.name if address.country else None,
        'country_iso': address.country.iso_code if address.country else None,
    }


def get_connection_request_billing_address(connection_request):
    """Adreça on s'envia la factura d'una sol·licitud d'escomesa.

    Per ordre: l'adreça de facturació triada a la sol·licitud, l'adreça de
    notificació de la persona (les actives, primer les de facturació) i, si no
    en té cap, l'adreça de l'escomesa. Torna un dict amb address, postal_code,
    city, province, country i country_iso, o None si no hi ha res.
    """
    person_address = connection_request.address_billing
    if person_address and person_address.address:
        return get_address_fields(person_address.address)

    holder = connection_request.person
    if holder:
        person_address = (
            holder.addresses.filter(is_active=True, address__isnull=False)
            .select_related('address__city', 'address__province', 'address__country')
            .order_by('-is_billing', 'id')
            .first()
        )
        if person_address:
            return get_address_fields(person_address.address)

    return _connection_request_location(connection_request)


def format_location(fields):
    """«CP Municipi, Província - País», el format de location_final de la factura."""
    location = ' '.join(filter(None, [fields['postal_code'], fields['city']]))
    if fields['province']:
        location = f"{location}, {fields['province']}"
    if fields['country']:
        location = f"{location} - {fields['country']}"
    return location


def get_connection_request_supply_address(connection_request):
    """Adreça de l'escomesa en una línia (carrer, número i municipi), o None."""
    location = _connection_request_location(connection_request)
    if not location:
        return None
    return ', '.join(filter(None, [location['address'], location['city']]))


def get_connection_request_reference(connection_request):
    """(tipus, número) que identifica la factura en lloc del contracte.

    Si la sol·licitud ja té escomesa, el número de l'escomesa; si no, el de la
    sol·licitud.
    """
    connection = connection_request.connection
    if connection and connection.token:
        return 'connection', connection.token
    return 'connection_request', connection_request.token
