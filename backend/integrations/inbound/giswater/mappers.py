from decimal import Decimal


def _decimal_value(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return value


def _person_full_name(person):
    if not person:
        return None
    parts = [person.name or "", person.surname or ""]
    full_name = " ".join(part for part in parts if part).strip()
    return full_name or None


def map_connection(connection):
    if not connection:
        return None

    diameter = connection.diameter
    exploitation = connection.exploitation
    dma = connection.dma

    return {
        "token": connection.token,
        "code_gis": connection.code_gis,
        "exploitation_token": exploitation.token if exploitation else None,
        "diameter": diameter.token if diameter else None,
        "dma_token": dma.token if dma else None,
        "latitude": _decimal_value(connection.latitude),
        "longitude": _decimal_value(connection.longitude),
    }


def map_supply_point(supply_point):
    if not supply_point:
        return None

    address = supply_point.address
    meter = supply_point.meter
    return {
        "token": supply_point.token,
        "address": address.address_search if address else None,
        "meter_code": meter.code if meter else None,
    }


def map_contract(contract):
    holder = contract.holder
    return {
        "token": contract.token,
        "holder": {
            "name": holder.name if holder else None,
            "surname": holder.surname if holder else None,
        },
        "holder_full_name": _person_full_name(holder),
    }


def map_contract_export(contract):
    supply_point = contract.supply_point_default
    connection = supply_point.connection if supply_point else None

    return {
        "connection": map_connection(connection),
        "supply_point": map_supply_point(supply_point),
        "contract": map_contract(contract),
    }


def map_reading(reading):
    meter = reading.meter
    supply_point = reading.supply_point

    return {
        "id": reading.id,
        "meter_code": meter.code if meter else None,
        "reading_date": reading.reading_date.isoformat() if reading.reading_date else None,
        "reading_value": _decimal_value(reading.reading_value),
        "consumption": _decimal_value(reading.calculated_value),
        "is_control": reading.is_control,
        "origin": reading.origin,
        "is_estimated": reading.is_estimated,
        "estimated_used": _decimal_value(reading.estimated_used),
        "supply_point_token": supply_point.token if supply_point else None,
        "consumption_days": reading.consumption_days,
        "billing_consumption": _decimal_value(reading.real_consumption),
    }
