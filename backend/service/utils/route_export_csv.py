from documentmanager.utils.csv_safety import SafeCsvWriter
from io import StringIO

from django.db.models import Q
from django.utils.translation import gettext as _

from service.models import Property, SupplyPoint
from service.utils.route_scope import position_supply_points_q


def _property_label(prop):
    if prop.name:
        return prop.name
    if prop.address_street:
        number = prop.address_street_number.number if prop.address_street_number else ''
        return f"{prop.address_street.name} {number}".strip()
    return prop.token or f"Property {prop.id}"


def _supply_point_label(supply_point):
    return supply_point.token or supply_point.name or f"SupplyPoint {supply_point.id}"


def build_route_export_headers():
    return [_('Ordre'), _('Codi de posició'), _('Finques'), _('Punts de subministrament'), _('Observació')]


def route_position_row_values(route_position):
    # Punts que pertanyen efectivament a la posició (propis o heretats de la
    # finca) i les seves finques; també les finques de la posició sense punts.
    supply_points = list(
        SupplyPoint.objects.filter(position_supply_points_q(route_position)).order_by('id')
    )
    property_ids = {sp.property_id for sp in supply_points if sp.property_id}
    properties = list(
        Property.objects.filter(is_active=True).filter(
            Q(id__in=property_ids) | Q(route_position=route_position, supply_points__isnull=True)
        ).distinct()
    )
    farm_labels = [_property_label(prop) for prop in properties]
    supply_point_labels = []
    for prop in properties:
        for supply_point in supply_points:
            if supply_point.property_id == prop.id and supply_point.is_active:
                supply_point_labels.append(_supply_point_label(supply_point))

    return [
        route_position.position if route_position.position is not None else '',
        route_position.token or '',
        ', '.join(farm_labels),
        ', '.join(supply_point_labels),
        route_position.reader_observation or '',
    ]


def build_route_export_csv_bytes(route):
    """
    CSV (UTF-8 amb BOM, delimitador ';') amb totes les RoutePosition d'una Route,
    amb les seves Finques (Property) i Punts de subministrament (SupplyPoint).
    """
    buffer = StringIO()
    buffer.write('﻿')
    writer = SafeCsvWriter(buffer, delimiter=';')
    writer.writerow(build_route_export_headers())

    positions = route.positions.all().order_by('position')
    for route_position in positions.iterator(chunk_size=500):
        writer.writerow(route_position_row_values(route_position))

    return buffer.getvalue().encode('utf-8')
