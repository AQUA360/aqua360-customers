from django.utils.dateparse import parse_datetime

from coredata.models import ConfigProject
from integrations.models import IntegrationRequestLog, SendBatch, SendBatchStatus
from integrations.utils.send_batch_status import payload_is_final_batch_result

PROVIDER = "odoo"
CALLBACK_ENDPOINT = "/odoo/v1/batch-results/"


class OdooBatchCallbackError(Exception):
    def __init__(self, detail, status_code=400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def log_odoo_batch_callback(
    payload,
    *,
    success,
    status_code,
    error_message="",
    response_payload=None,
    object_id="",
):
    IntegrationRequestLog.objects.create(
        provider=PROVIDER,
        direction=IntegrationRequestLog.DIRECTION_INBOUND,
        method="POST",
        endpoint=CALLBACK_ENDPOINT,
        request_payload=payload,
        response_payload=response_payload,
        status_code=status_code,
        success=success,
        error_message=error_message,
        object_type="send_batch",
        object_id=object_id or (payload or {}).get("batch_id", ""),
    )


def _parse_dt(value):
    if not value:
        return None
    return parse_datetime(value)


def apply_odoo_batch_result(payload: dict) -> dict:
    """
    Desa/actualitza la resposta final d'un lot.

    El cos és el mateix JSON que GET /aqua360/batch/{batch_id}.
    Si arriba un reprocessament (mateix batch_id, finished_at més recent),
    es queda amb el més nou.

    Quan la resposta és tractable (results/summary/finished_at…), l'estat
    del lot passa a finalized (token 2), independentment dels errors d'ítems
    o del valor `status` que enviï el proveïdor.
    """
    if not isinstance(payload, dict):
        raise OdooBatchCallbackError("Request body must be a JSON object.")

    batch_id = (payload.get("batch_id") or "").strip()
    if not batch_id:
        raise OdooBatchCallbackError("batch_id is required.")

    try:
        batch = SendBatch.objects.select_related("status").get(token=batch_id)
    except SendBatch.DoesNotExist as exc:
        raise OdooBatchCallbackError(
            f"Batch not found for batch_id '{batch_id}'.",
            status_code=404,
        ) from exc

    incoming_finished_at = _parse_dt(payload.get("finished_at"))
    if (
        batch.finished_at
        and incoming_finished_at
        and incoming_finished_at < batch.finished_at
    ):
        return {
            "batch_id": batch.token,
            "accepted": False,
            "reason": "stale_finished_at",
            "status": batch.status.token if batch.status else None,
        }

    if payload_is_final_batch_result(payload):
        try:
            token = ConfigProject.objects.get(
                token="send_batch_status_finalized_token"
            ).value
            batch.status = SendBatchStatus.objects.get(token=token)
        except (ConfigProject.DoesNotExist, SendBatchStatus.DoesNotExist):
            pass

    batch.received_at = _parse_dt(payload.get("received_at")) or batch.received_at
    batch.finished_at = incoming_finished_at or batch.finished_at
    batch.summary = payload.get("summary") if "summary" in payload else batch.summary
    batch.final_response = payload
    batch.save(
        update_fields=[
            "status",
            "received_at",
            "finished_at",
            "summary",
            "final_response",
            "updated_at",
        ]
    )

    return {
        "batch_id": batch.token,
        "accepted": True,
        "status": batch.status.name if batch.status else None,
        "finished_at": batch.finished_at.isoformat() if batch.finished_at else None,
    }
