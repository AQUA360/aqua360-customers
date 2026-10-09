from ..models import Route, RoutePosition
from coredata.models import ConfigProject
from django.db.models import Count, Sum
from .property_route_service import sync_property_tokens_with_route_position


def build_route_position_token(route_position):
    """Retorna l'Ident. que li correspon a una posició de ruta segons el
    seu ordre: {token_ruta}_{posicio} (p.ex. 888_1)."""
    if not route_position or not route_position.route_id:
        return route_position.token if route_position else None
    return f"{route_position.route.token}_{route_position.position or 0}"


def regenerate_route_position_token(route_position):
    """Manté l'Ident. (token) de la posició de ruta sincronitzat amb el seu
    ordre actual. S'ha de cridar sempre que la posició canvia (reordenació),
    no en la creació inicial (el frontend ja l'assigna en crear-la)."""
    new_token = build_route_position_token(route_position)
    if new_token and route_position.token != new_token:
        route_position.token = new_token
        route_position.save(update_fields=['token'])


def route_position_change(route_id, current_position, exclude_id=None):
    print("In route_position_change")
    route = Route.objects.get(id=route_id)
    #TODO: set every higher position to +1
    route_positions = RoutePosition.objects.filter(route=route)
    if exclude_id:
        route_positions = route_positions.exclude(id=exclude_id)

    for route_position in route_positions:
        if route_position.position and route_position.position >= current_position:
            route_position.position = route_position.position + 1
            route_position.save()
            regenerate_route_position_token(route_position)
            sync_property_tokens_with_route_position(route_position)

    return route

def route_count_total_readings(route):
    num_total_readings = 0
    for position in route.positions.all():
        if position.properties.count() > 0:
            num_total_readings += position.properties.annotate(num_supplypoints=Count('supply_points')).aggregate(total=Sum('num_supplypoints'))['total']
    return num_total_readings