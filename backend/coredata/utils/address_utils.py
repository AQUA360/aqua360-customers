#
#
#

def get_address_complete_without_city(address):
    number_display = str(address.street_number) if address.street_number else ''
    
    floor_door = []
    if address.floor:
        floor_door.append(address.floor)
    if address.door:
        floor_door.append(address.door)
    
    return f"{str(address.street)}, {number_display if number_display else ''} {address.building if address.building else ''} {address.stair if address.stair else ''} {'-'.join(floor_door) if floor_door else ''}".strip()

def get_address_complete_with_city(address):
    number_display = str(address.street_number) if address.street_number else ''
    
    floor_door = []
    if address.floor:
        floor_door.append(address.floor)
    if address.door:
        floor_door.append(address.door)
    
    #check if country is Spain or if Address is from SupplyPoint class
    if (address.country and address.country.iso_code == 'ES'):
        return f"{str(address.street)}, {number_display if number_display else ''} {address.building if address.building else ''} {address.stair if address.stair else ''} {'-'.join(floor_door if floor_door else [''])}, {address.city}".strip()
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
            
        return f"{address.street}{', ' + str(number_display) if number_display else ''} {address.stair if address.stair else ''} {'-'.join(floor_door)} - {postal_code} - {city} - {country}".strip()


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