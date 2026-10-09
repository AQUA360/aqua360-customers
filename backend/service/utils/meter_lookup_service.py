"""
Lookup de comptadors per llista de meter.code: found / not_found + builders CSV.
"""
import csv
from io import StringIO

from django.db.models import Prefetch

from billing.models import Reading
from contract.models import Contract
from service.models import Meter, SupplyPoint


def normalize_meter_codes(codes):
    """Strip, drop empties, dedupe preservant ordre d'aparició."""
    seen = set()
    result = []
    for raw in codes or []:
        code = str(raw).strip() if raw is not None else ''
        if not code or code in seen:
            continue
        seen.add(code)
        result.append(code)
    return result


def _status_brief(status):
    if not status:
        return None
    return {
        'id': status.id,
        'token': status.token,
        'name': status.name,
        'color': getattr(status, 'color', None),
    }


def _status_label(status):
    if not status:
        return ''
    return (status.name or status.token or '').strip()


def _primary_supply_point(meter):
    if hasattr(meter, 'active_supply_points') and meter.active_supply_points:
        return meter.active_supply_points[0]
    return meter.supply_points.filter(is_active=True).first()


def _address_search(supply_point):
    if not supply_point or not supply_point.address:
        return ''
    return (getattr(supply_point.address, 'address_search', None) or str(supply_point.address) or '').strip()


def _contracts_for_supply_point(supply_point):
    if not supply_point:
        return []
    contracts = list(supply_point.contracts.all())
    contracts.sort(key=lambda c: ((c.token or '').lower(), c.id or 0))
    return contracts


def _contract_payload(contract):
    return {
        'token': contract.token,
        'status': _status_brief(contract.status),
        'facturable': not bool(contract.block_billing),
    }


def _last_reading_for_meter(meter, readings_by_meter=None):
    if readings_by_meter is not None:
        return readings_by_meter.get(meter.id)
    return (
        Reading.objects.filter(
            meter=meter,
            is_active=True,
            is_control=False,
        )
        .select_related('batch')
        .order_by('-reading_date', '-id')
        .first()
    )


def meter_to_lookup_dict(meter, readings_by_meter=None):
    supply_point = _primary_supply_point(meter)
    contracts = _contracts_for_supply_point(supply_point)
    last_reading = _last_reading_for_meter(meter, readings_by_meter)

    exploitation = None
    if supply_point and supply_point.connection and supply_point.connection.exploitation:
        exploitation = supply_point.connection.exploitation.name

    reading_payload = None
    if last_reading:
        reading_payload = {
            'reading_date': last_reading.reading_date,
            'reading_value': last_reading.reading_value,
            'consumption': last_reading.calculated_value,
            'batch_token': last_reading.batch.token if last_reading.batch else None,
        }

    return {
        'id': meter.id,
        'code': meter.code,
        'exploitation': exploitation,
        'status': _status_brief(meter.status),
        'caliber': (
            {
                'token': meter.caliber.token,
                'name': meter.caliber.name,
            }
            if meter.caliber
            else None
        ),
        'installation_at': meter.installation_at,
        'uninstallation_at': meter.uninstallation_at,
        'has_remote_reading': meter.has_remote_reading,
        'manufacturer': meter.manufacturer,
        'manufacturing_year': meter.manufacturing_year,
        'comm_technology': meter.comm_technology,
        'supply_point': (
            {
                'token': supply_point.token,
                'status': _status_brief(supply_point.status),
                'address_search': _address_search(supply_point),
            }
            if supply_point
            else None
        ),
        'contracts': [_contract_payload(c) for c in contracts],
        'last_reading': reading_payload,
    }


def get_meters_queryset_for_codes(codes):
    return (
        Meter.objects.filter(code__in=codes)
        .select_related('status', 'caliber')
        .prefetch_related(
            Prefetch(
                'supply_points',
                queryset=SupplyPoint.objects.filter(is_active=True)
                .select_related(
                    'status',
                    'address',
                    'connection',
                    'connection__exploitation',
                )
                .prefetch_related(
                    Prefetch(
                        'contracts',
                        queryset=Contract.objects.select_related('status').order_by(
                            'token', 'id'
                        ),
                    )
                ),
                to_attr='active_supply_points',
            )
        )
    )


def get_last_readings_by_meter_ids(meter_ids):
    """Una lectura no-control activa per meter (la més recent)."""
    if not meter_ids:
        return {}
    readings = (
        Reading.objects.filter(
            meter_id__in=meter_ids,
            is_active=True,
            is_control=False,
        )
        .select_related('batch')
        .order_by('meter_id', '-reading_date', '-id')
    )
    by_meter = {}
    for reading in readings.iterator(chunk_size=2000):
        if reading.meter_id not in by_meter:
            by_meter[reading.meter_id] = reading
    return by_meter


def lookup_meters_by_codes(codes):
    """
    Retorna (found_dicts, not_found_codes) preservant l'ordre d'entrada.
    """
    normalized = normalize_meter_codes(codes)
    if not normalized:
        return [], []

    meters = list(get_meters_queryset_for_codes(normalized))
    meters_by_code = {m.code: m for m in meters if m.code}
    readings_by_meter = get_last_readings_by_meter_ids([m.id for m in meters])

    found = []
    not_found = []
    for code in normalized:
        meter = meters_by_code.get(code)
        if meter:
            found.append(meter_to_lookup_dict(meter, readings_by_meter))
        else:
            not_found.append(code)

    return found, not_found


def build_meter_lookup_csv_headers(max_contracts):
    headers = [
        'Code',
        'Found',
        'Exploitation',
        'Status',
        'Caliber',
        'InstallationAt',
        'UninstallationAt',
        'HasRemoteReading',
        'Manufacturer',
        'ManufacturingYear',
        'CommTechnology',
        'SupplyPoint[Token]',
        'SupplyPoint[Status]',
        'SupplyPoint[AddressSearch]',
        'LastReading[ReadingDate]',
        'LastReading[ReadingValue]',
        'LastReading[Consumption]',
        'LastReading[BatchToken]',
    ]
    for index in range(max_contracts):
        headers.append(f'Contract[{index}][Token]')
        headers.append(f'Contract[{index}][Status]')
        headers.append(f'Contract[{index}][Facturable]')
    return headers


def _format_date(value):
    if not value:
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime('%Y-%m-%d')
    return str(value)


def _format_value(value):
    if value is None:
        return ''
    return str(value)


def build_meter_lookup_csv_row(code, meter_dict, max_contracts):
    if not meter_dict:
        return [code, 'No'] + [''] * (16 + max_contracts * 3)

    status = meter_dict.get('status') or {}
    caliber = meter_dict.get('caliber') or {}
    supply_point = meter_dict.get('supply_point') or {}
    sp_status = supply_point.get('status') or {}
    last_reading = meter_dict.get('last_reading') or {}
    contracts = meter_dict.get('contracts') or []

    row = [
        meter_dict.get('code') or code,
        'Sí',
        meter_dict.get('exploitation') or '',
        status.get('name') or status.get('token') or '',
        caliber.get('name') or caliber.get('token') or '',
        _format_date(meter_dict.get('installation_at')),
        _format_date(meter_dict.get('uninstallation_at')),
        'Sí' if meter_dict.get('has_remote_reading') else 'No',
        meter_dict.get('manufacturer') or '',
        _format_value(meter_dict.get('manufacturing_year')),
        meter_dict.get('comm_technology') or '',
        supply_point.get('token') or '',
        sp_status.get('name') or sp_status.get('token') or '',
        supply_point.get('address_search') or '',
        _format_date(last_reading.get('reading_date')),
        _format_value(last_reading.get('reading_value')),
        _format_value(last_reading.get('consumption')),
        last_reading.get('batch_token') or '',
    ]
    for index in range(max_contracts):
        if index < len(contracts):
            contract = contracts[index]
            c_status = contract.get('status') or {}
            row.append(contract.get('token') or '')
            row.append(c_status.get('name') or c_status.get('token') or '')
            row.append('True' if contract.get('facturable') else 'False')
        else:
            row.extend(['', '', ''])
    return row


def build_meter_lookup_csv_bytes(codes):
    found, not_found = lookup_meters_by_codes(codes)
    found_by_code = {item['code']: item for item in found if item.get('code')}

    max_contracts = 0
    for item in found:
        max_contracts = max(max_contracts, len(item.get('contracts') or []))

    normalized = normalize_meter_codes(codes)
    buffer = StringIO()
    buffer.write('\ufeff')
    writer = csv.writer(buffer, delimiter=';')
    writer.writerow(build_meter_lookup_csv_headers(max_contracts))

    for code in normalized:
        meter_dict = found_by_code.get(code)
        writer.writerow(build_meter_lookup_csv_row(code, meter_dict, max_contracts))

    return buffer.getvalue().encode('utf-8'), len(found), len(not_found)
