from contract.models import Contract
from billing.models import Reading
from integrations.models import IntegrationRequestLog

from .mappers import map_contract_export, map_reading

PROVIDER = "giswater"
CONTRACTS_ENDPOINT = "/giswater/v1/contracts/"
READINGS_ENDPOINT = "/giswater/v1/contracts/{contract_token}/readings/"


class GiswaterInboundError(Exception):
    def __init__(self, detail, status_code=400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _contracts_queryset(*, connection_token=None, connection_code_gis=None):
    queryset = Contract.objects.select_related(
        "holder",
        "supply_point_default",
        "supply_point_default__connection",
        "supply_point_default__connection__exploitation",
        "supply_point_default__connection__diameter",
        "supply_point_default__connection__dma",
        "supply_point_default__address",
        "supply_point_default__address__street",
        "supply_point_default__address__city",
        "supply_point_default__meter",
    ).order_by("id")

    connection_token = (connection_token or "").strip() or None
    connection_code_gis = (connection_code_gis or "").strip() or None

    if connection_token:
        queryset = queryset.filter(supply_point_default__connection__token=connection_token)
    if connection_code_gis:
        queryset = queryset.filter(supply_point_default__connection__code_gis=connection_code_gis)

    return queryset


def fetch_contracts_export(*, connection_token=None, connection_code_gis=None):
    return [
        map_contract_export(contract)
        for contract in _contracts_queryset(
            connection_token=connection_token,
            connection_code_gis=connection_code_gis,
        )
    ]


def fetch_contract_readings(contract_token):
    token = (contract_token or "").strip()
    if not token:
        raise GiswaterInboundError("contract_token és obligatori.", status_code=400)

    contract = Contract.objects.filter(token=token).only("id", "token").first()
    if not contract:
        raise GiswaterInboundError("Contracte no trobat.", status_code=404)

    readings = (
        Reading.objects.filter(contract_id=contract.id, is_active=True)
        .select_related("meter", "supply_point")
        .order_by("-reading_date", "-id")
    )
    return [map_reading(reading) for reading in readings]


def log_inbound_request(
    *,
    endpoint,
    method,
    request_payload=None,
    response_payload=None,
    status_code,
    success,
    error_message="",
    object_type="",
    object_id="",
):
    IntegrationRequestLog.objects.create(
        provider=PROVIDER,
        direction=IntegrationRequestLog.DIRECTION_INBOUND,
        method=method,
        endpoint=endpoint,
        request_payload=request_payload,
        response_payload=response_payload,
        status_code=status_code,
        success=success,
        error_message=error_message,
        object_type=object_type,
        object_id=object_id,
    )
