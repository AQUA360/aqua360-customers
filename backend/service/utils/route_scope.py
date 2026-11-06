"""
Ruta efectiva dels punts de subministrament.

Un punt de subministrament pot tenir una posició de ruta pròpia
(SupplyPoint.route_position). Si no en té, segueix la de la seva finca
(Property.route_position). Aquest mòdul centralitza aquesta regla perquè els
lots de lectura, la LecturApp, els exports i els informes no tornin a
calcular-la cadascun pel seu compte.

Les funcions *_q retornen un Q aplicable a un queryset de SupplyPoint, o a un
queryset d'un altre model que hi arribi a través de `prefix` (p. ex.
prefix='supply_point__' per a Reading o Contract).
"""
from django.db.models import Case, F, Q, When
from django.db.models.functions import Coalesce


def effective_route_q(lookup, value, prefix=''):
    """Q per filtrar punts per un camp de la seva posició de ruta efectiva.

    `lookup` és relatiu a RoutePosition: p. ex. 'route', 'route__in',
    'route__reading_batches', 'route__route_zone__in', 'isnull'...
    """
    own = Q(**{f'{prefix}route_position__{lookup}': value})
    inherited = Q(**{
        f'{prefix}route_position__isnull': True,
        f'{prefix}property__route_position__{lookup}': value,
    })
    return own | inherited


def route_supply_points_q(route, prefix=''):
    """Punts que pertanyen a `route` (instància o id)."""
    return effective_route_q('route', route, prefix)


def routes_supply_points_q(routes, prefix=''):
    """Punts que pertanyen a qualsevol de les rutes (queryset o llista d'ids)."""
    return effective_route_q('route__in', routes, prefix)


def reading_batch_supply_points_q(reading_batch, prefix=''):
    """Punts de les rutes d'un lot de lectura."""
    return effective_route_q('route__reading_batches', reading_batch, prefix)


def position_supply_points_q(position, prefix=''):
    """Punts que pertanyen a una posició de ruta concreta."""
    own = Q(**{f'{prefix}route_position': position})
    inherited = Q(**{
        f'{prefix}route_position__isnull': True,
        f'{prefix}property__route_position': position,
    })
    return own | inherited


def effective_route_position_expr(prefix=''):
    """Expressió amb l'id de la posició de ruta efectiva del punt.

    Serveix per anotar un queryset de SupplyPoint (o d'un model que hi arribi
    amb `prefix`) i agrupar o filtrar per posició, p. ex.
    `.annotate(pos=effective_route_position_expr()).values('pos')`.
    """
    return Coalesce(
        F(f'{prefix}route_position'),
        F(f'{prefix}property__route_position'),
    )


def effective_route_field_expr(field, prefix=''):
    """Expressió amb un camp de la posició de ruta efectiva del punt.

    `field` és relatiu a RoutePosition (p. ex. 'route__token', 'position').
    Per a .values()/.annotate() d'informes, en lloc de
    `property__route_position__<field>`.
    """
    return Case(
        When(**{f'{prefix}route_position__isnull': False}, then=F(f'{prefix}route_position__{field}')),
        default=F(f'{prefix}property__route_position__{field}'),
    )


def effective_route_ids(supply_points):
    """Subconsulta amb els ids de les rutes efectives d'un queryset de
    SupplyPoint (sense nuls), per filtrar Route amb `id__in`."""
    return supply_points.annotate(
        effective_route_id=effective_route_field_expr('route'),
    ).filter(effective_route_id__isnull=False).values('effective_route_id')


def without_route_q(prefix=''):
    """Punts sense cap ruta efectiva (ni pròpia ni de la finca)."""
    return Q(**{f'{prefix}route_position__isnull': True}) & (
        Q(**{f'{prefix}property__isnull': True})
        | Q(**{f'{prefix}property__route_position__isnull': True})
    )


def with_route_q(prefix=''):
    """Punts amb ruta efectiva."""
    return Q(**{f'{prefix}route_position__isnull': False}) | Q(
        **{f'{prefix}property__route_position__isnull': False}
    )


def effective_route_position(supply_point):
    """RoutePosition efectiva d'un punt (o None)."""
    if supply_point is None:
        return None
    if supply_point.route_position_id:
        return supply_point.route_position
    if supply_point.property_id and supply_point.property:
        return supply_point.property.route_position
    return None


def effective_route(supply_point):
    """Route efectiva d'un punt (o None)."""
    route_position = effective_route_position(supply_point)
    if route_position is None or not route_position.route_id:
        return None
    return route_position.route


def has_own_route_position(supply_point):
    """True si el punt té una posició de ruta pròpia (no heretada de la finca)."""
    return bool(supply_point and supply_point.route_position_id)


def serialize_effective_route(supply_point):
    route_position = effective_route_position(supply_point)
    if route_position is None:
        return None
    route = route_position.route if route_position.route_id else None
    zone = route.route_zone if route and route.route_zone_id else None
    return {
        'route_id': route.id if route else None,
        'route_token': route.token if route else None,
        'route_name': route.name if route else None,
        'route_zone_name': zone.name if zone else None,
        'position_id': route_position.id,
        'position': route_position.position,
        'position_token': route_position.token,
        'inherited': not supply_point.route_position_id,
    }


# select_related per evitar consultes en cridar effective_route_position().
EFFECTIVE_ROUTE_SELECT_RELATED = (
    'route_position',
    'route_position__route',
    'property__route_position',
    'property__route_position__route',
)


def effective_route_select_related(prefix=''):
    return [f'{prefix}{path}' for path in EFFECTIVE_ROUTE_SELECT_RELATED]
