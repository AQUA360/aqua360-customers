import re
from service.models import Property, RoutePosition, Route


def sync_property_tokens_with_route_position(route_position):
    """No-op per defecte. Es pot personalitzar per client (veure el bloc
    try/except al final del mòdul) per fer que l'identificador (token) de
    les finques d'una posició de ruta segueixi el patró número_ruta_posició.
    """
    pass

def extract_integer_from_street_number(street_number):
    if street_number is None:
        return None
    if isinstance(street_number, int):
        return street_number
    street_number_str = str(street_number)
    match = re.search(r'\d+', street_number_str)
    if match:
        return int(match.group())
    return None

def clean_street_name_for_search(street_name):
    if not street_name:
        return street_name
    clean_name = street_name.strip()
    if ',' in clean_name:
        clean_name = clean_name.split(',', 1)[0].strip()
    combined_pattern = r'^\s*(C|AV|AVENIDA|CARRER|PL|PLAZA|PG|PASSEIG|PS)\s*[./\s]+\s*(D\'|DE\s+|DEL\s+|DE\s+LA\s+|DE\s+LES\s+|DE\s+ELS\s+)'
    clean_name = re.sub(combined_pattern, '', clean_name, flags=re.IGNORECASE)
    if '/' in clean_name or '.' in clean_name:
        part = clean_name.split('/', 1)[1].strip() if '/' in clean_name else clean_name.split('.', 1)[1].strip()
        clean_name = part.strip()
    street_type_pattern = r'^\s*(C|AV|AVENIDA|CARRER|PL|PLAZA|PG|PASSEIG|PS)\s*[./\s]*\s*'
    clean_name = re.sub(street_type_pattern, '', clean_name, flags=re.IGNORECASE)
    preposition_pattern = r'^\s*(D\'|DE\s+|DEL\s+|DE\s+LA\s+|DE\s+LES\s+|DE\s+ELS\s+)'
    clean_name = re.sub(preposition_pattern, '', clean_name, flags=re.IGNORECASE)
    return clean_name.strip()

def auto_assign_route_to_property(property_obj):
    """
    Tries to find the best route for a property by looking at other properties on the same street.
    """
    if property_obj.route_position:
        return property_obj.route_position

    street = property_obj.address_street
    city = property_obj.address_city
    
    if not street or not city:
        return None

    # Try to find a RoutePosition in the same street and city
    # We use a similar logic to the watchdog script
    clean_name = clean_street_name_for_search(street.name)
    
    # First, try exact street match
    nearby_rp = RoutePosition.objects.filter(
        address_street=street,
        address_city=city,
        route__isnull=False
    ).select_related('route').first()

    # If no exact match, try fuzzy name match
    if not nearby_rp and clean_name:
        nearby_rp = RoutePosition.objects.filter(
            address_street__name__icontains=clean_name,
            address_city=city,
            route__isnull=False
        ).select_related('route').first()

    if nearby_rp:
        route = nearby_rp.route
        # Create a new RoutePosition for this property
        new_rp = RoutePosition.objects.create(
            position=0,
            route=route,
            token=f"{route.token}/{property_obj.token or property_obj.id}",
            address_street=property_obj.address_street,
            address_street_number=property_obj.address_street_number,
            address_city=property_obj.address_city,
            address_postal_code=property_obj.address_postal_code,
            latitude=property_obj.latitude,
            longitude=property_obj.longitude
        )
        property_obj.route_position = new_rp
        property_obj.save()
        sync_property_tokens_with_route_position(new_rp)
        return new_rp

    return None


# Permet personalitzar per client: si existeix property_route_service_personalized,
# s'usa la seva sync_property_tokens_with_route_position en lloc de la d'aquest mòdul.
try:
    from service.utils import property_route_service_personalized
    if hasattr(property_route_service_personalized, 'sync_property_tokens_with_route_position'):
        sync_property_tokens_with_route_position = property_route_service_personalized.sync_property_tokens_with_route_position
except ImportError:
    pass
