def _customer_name(person):
    if not person:
        return None
    parts = [person.name or "", person.surname or ""]
    full_name = " ".join(part for part in parts if part).strip()
    return full_name or None


def map_abonat(contract, *, active_status_token=None):
    """Payload equivalent a `vw_abonats_aqua360`, resolt des dels models Django."""
    supply_point = contract.supply_point_default
    meter = supply_point.meter if supply_point else None
    address = supply_point.address if supply_point else None
    connection = supply_point.connection if supply_point else None
    exploitation = connection.exploitation if connection else None
    dma = connection.dma if connection else None
    status = contract.status

    return {
        "policy": contract.token,
        "meter": meter.code if meter else None,
        "rate": contract.use_type.name if contract.use_type else None,
        "service_point": address.address_search if address else None,
        "inst_date": meter.installation_at.isoformat() if meter and meter.installation_at else None,
        "comm_module": meter.comm_module if meter else None,
        "comm_technology": meter.comm_technology if meter else None,
        "manufacturer": meter.manufacturer if meter else None,
        "model": meter.model if meter else None,
        "network_provider": meter.network_provider if meter else None,
        "expl_id": exploitation.token if exploitation else None,
        "dma_id": dma.token if dma else None,
        "contract_active": bool(
            status and active_status_token and status.token == active_status_token
        ),
        "customer": _customer_name(contract.holder),
        "cadastral_ref": supply_point.cadastral if supply_point else None,
        "connect_id": str(connection.id) if connection else None,
    }
