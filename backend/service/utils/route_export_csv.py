import csv
from io import StringIO

from django.utils.translation import gettext as _


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
    properties = list(route_position.properties.filter(is_active=True))
    farm_labels = [_property_label(prop) for prop in properties]
    supply_point_labels = []
    for prop in properties:
        for supply_point in prop.supply_points.filter(is_active=True):
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
    writer = csv.writer(buffer, delimiter=';')
    writer.writerow(build_route_export_headers())

    positions = route.positions.all().order_by('position').prefetch_related('properties__supply_points')
    for route_position in positions.iterator(chunk_size=500):
        writer.writerow(route_position_row_values(route_position))

    return buffer.getvalue().encode('utf-8')
