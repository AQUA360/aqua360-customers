from contract.models import Contract
from coredata.models import ConfigProject
from integrations.models import IntegrationRequestLog

from .serializers import SmartMeteringAbonatSerializer

PROVIDER = "smartmetering"
CONTRACTS_ENDPOINT = "/smartmetering/v1/contracts/"
ACTIVE_STATUS_CONFIG_TOKEN = "contract_active_token"


def _active_contract_status_token():
    value = (
        ConfigProject.objects.filter(token=ACTIVE_STATUS_CONFIG_TOKEN)
        .values_list("value", flat=True)
        .first()
    )
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _contracts_queryset(*, policy=None, meter=None):
    queryset = (
        Contract.objects.filter(is_active=True)
        .select_related(
            "holder",
            "status",
            "use_type",
            "supply_point_default",
            "supply_point_default__meter",
            "supply_point_default__address",
            "supply_point_default__connection",
            "supply_point_default__connection__exploitation",
            "supply_point_default__connection__dma",
        )
        .order_by("id")
    )

    policy = (policy or "").strip() or None
    meter = (meter or "").strip() or None

    if policy:
        queryset = queryset.filter(token=policy)
    if meter:
        queryset = queryset.filter(supply_point_default__meter__code=meter)

    return queryset


def fetch_contracts_export(*, policy=None, meter=None):
    active_status_token = _active_contract_status_token()
    serializer = SmartMeteringAbonatSerializer(
        _contracts_queryset(policy=policy, meter=meter),
        many=True,
        context={"active_status_token": active_status_token},
    )
    return serializer.data


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
