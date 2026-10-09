"""
CSV de SupplyPoints d'una Route (o d'un ReadingBatch via les seves Routes)
amb lectura opcional i contractes.
"""
import csv
from io import StringIO

from django.db.models import Prefetch

from contract.models import Contract
from service.models import Route, SupplyPoint


def _status_label(status):
    if not status:
        return ''
    return (status.name or status.token or '').strip()


def _meter_label(meter):
    if not meter:
        return ''
    return (meter.code or meter.token or '').strip()


def _format_date(value):
    if not value:
        return ''
    return value.strftime('%d/%m/%Y')


def _format_decimal(value):
    if value is None:
        return ''
    return str(value)


def _route_position_from_supply_point(supply_point):
    prop = getattr(supply_point, 'property', None)
    if not prop:
        return None
    return getattr(prop, 'route_position', None)


def _route_location_values(supply_point):
    """Route / RoutePosition / Property des de property.route_position."""
    prop = getattr(supply_point, 'property', None)
    route_position = _route_position_from_supply_point(supply_point)
    route = getattr(route_position, 'route', None) if route_position else None

    return [
        (route.token or '').strip() if route else '',
        (route.name or '').strip() if route else '',
        (route_position.token or '').strip() if route_position else '',
        str(route_position.position) if route_position and route_position.position is not None else '',
        (prop.token or '').strip() if prop else '',
    ]


def _contracts_for_supply_point(supply_point):
    contracts = list(supply_point.contracts.all())
    contracts.sort(key=lambda c: ((c.token or '').lower(), c.id or 0))
    return contracts


def _contract_facturable(contract):
    """Facturable = not block_billing (True/False com a text)."""
    return 'False' if contract.block_billing else 'True'


def build_supply_points_export_headers(max_contracts):
    headers = [
        'Route[Token]',
        'Route[Name]',
        'RoutePosition[Token]',
        'RoutePosition[Position]',
        'Property[Token]',
        'SupplyPoint[Token]',
        'SupplyPoint[Status]',
        'Meter[Code]',
        'HasReading',
        'Reading[ReadingDate]',
        'Reading[ReadingValue]',
        'Reading[Consumption]',
    ]
    for index in range(max_contracts):
        headers.append(f'Contract[{index}][Token]')
        headers.append(f'Contract[{index}][Status]')
        headers.append(f'Contract[{index}][Facturable]')
    return headers


def build_supply_points_export_row(supply_point, reading, contracts, max_contracts):
    has_reading = reading is not None
    row = _route_location_values(supply_point) + [
        (supply_point.token or '').strip(),
        _status_label(supply_point.status),
        _meter_label(supply_point.meter),
        'Sí' if has_reading else 'No',
        _format_date(reading.reading_date) if has_reading else '',
        _format_decimal(reading.reading_value) if has_reading else '',
        _format_decimal(reading.calculated_value) if has_reading else '',
    ]
    for index in range(max_contracts):
        if index < len(contracts):
            contract = contracts[index]
            row.append((contract.token or '').strip())
            row.append(_status_label(contract.status))
            row.append(_contract_facturable(contract))
        else:
            row.extend(['', '', ''])
    return row


def _prefetch_supply_points_qs(qs):
    return (
        qs.select_related(
            'status',
            'meter',
            'property',
            'property__route_position',
            'property__route_position__route',
        )
        .prefetch_related(
            Prefetch(
                'contracts',
                queryset=Contract.objects.select_related('status').order_by('token', 'id'),
            )
        )
        .distinct()
        .order_by(
            'property__route_position__route__token',
            'property__route_position__position',
            'token',
            'id',
        )
    )


def get_supply_points_for_route(route):
    """SupplyPoints actius de la Route (totes les posicions / finques)."""
    qs = SupplyPoint.objects.filter(
        is_active=True,
        property__route_position__route=route,
    )
    return _prefetch_supply_points_qs(qs)


def get_supply_points_for_reading_batch(reading_batch):
    """
    SupplyPoints de les Routes del lot, amb el mateix filtre telecontrol/manual
    que ReadingBatchSetupViewSet.
    """
    qs = SupplyPoint.objects.filter(
        is_active=True,
        property__route_position__route__reading_batches=reading_batch,
    )

    if not reading_batch.include_telecontrol:
        qs = qs.filter(meter__has_remote_reading=False)
    elif not reading_batch.include_manual:
        qs = qs.filter(meter__has_remote_reading=True)

    return _prefetch_supply_points_qs(qs)


def get_readings_by_supply_point_for_batch(batch_id):
    """
    Una lectura no-control activa per SupplyPoint del lot (la més recent per data).
    """
    from billing.models import Reading

    readings = (
        Reading.objects.filter(
            batch_id=batch_id,
            is_active=True,
            is_control=False,
            supply_point_id__isnull=False,
        )
        .order_by('supply_point_id', '-reading_date', '-id')
    )
    by_sp = {}
    for reading in readings.iterator(chunk_size=2000):
        if reading.supply_point_id not in by_sp:
            by_sp[reading.supply_point_id] = reading
    return by_sp


def build_supply_points_csv_bytes(supply_points, readings_by_sp=None, empty_message=None):
    """
    Genera el CSV (UTF-8 amb BOM, delimitador ';').
    `readings_by_sp` és opcional (dict supply_point_id -> Reading).
    """
    supply_points = list(supply_points)
    if not supply_points:
        return None, empty_message or 'No s\'han trobat SupplyPoints'

    readings_by_sp = readings_by_sp or {}

    prepared_rows = []
    max_contracts = 0
    for supply_point in supply_points:
        contracts = _contracts_for_supply_point(supply_point)
        max_contracts = max(max_contracts, len(contracts))
        prepared_rows.append(
            (
                supply_point,
                readings_by_sp.get(supply_point.id),
                contracts,
            )
        )

    buffer = StringIO()
    buffer.write('\ufeff')
    writer = csv.writer(buffer, delimiter=';')
    writer.writerow(build_supply_points_export_headers(max_contracts))

    for supply_point, reading, contracts in prepared_rows:
        writer.writerow(
            build_supply_points_export_row(
                supply_point, reading, contracts, max_contracts
            )
        )

    return buffer.getvalue().encode('utf-8'), None


def build_route_supply_points_csv_bytes(route_id):
    """
    CSV dels SupplyPoints d'una Route (mateixes columnes que l'export per lot;
    sense lot, les columnes de Reading queden buides / HasReading=No).
    """
    try:
        route = Route.objects.get(id=route_id, is_active=True)
    except Route.DoesNotExist:
        return None, 'No s\'ha trobat la Route'

    return build_supply_points_csv_bytes(
        get_supply_points_for_route(route),
        readings_by_sp=None,
        empty_message='No s\'han trobat SupplyPoints a aquesta ruta',
    )


def build_reading_batch_supply_points_csv_bytes(batch_id):
    """
    CSV dels SupplyPoints de les Routes d'un ReadingBatch amb la lectura del lot.
    """
    from billing.models import ReadingBatch

    try:
        reading_batch = ReadingBatch.objects.get(id=batch_id, is_active=True)
    except ReadingBatch.DoesNotExist:
        return None, 'No s\'ha trobat el ReadingBatch'

    return build_supply_points_csv_bytes(
        get_supply_points_for_reading_batch(reading_batch),
        readings_by_sp=get_readings_by_supply_point_for_batch(batch_id),
        empty_message='No s\'han trobat SupplyPoints a les rutes d\'aquest batch',
    )
