import requests
from django.conf import settings
from django.utils import timezone

from integrations.models import IntegrationRequestLog

from .exceptions import OdooApiError

PROVIDER = "odoo"
TRANSPORT_FASTAPI = "fastapi"
TRANSPORT_JSON2 = "json2"
INVOICES_ENDPOINT = "/invoices"
PAYMENTS_ENDPOINT = "/payments"
JSON2_INVOICE_MODEL = "x_aqua_invoice"
JSON2_PAYMENT_MODEL = "x_aqua_payment"
JSON2_INVOICE_ENDPOINT = f"/json/2/{JSON2_INVOICE_MODEL}/create"
JSON2_PAYMENT_ENDPOINT = f"/json/2/{JSON2_PAYMENT_MODEL}/create"
JSON2_COMMITMENTS_UNSUPPORTED = (
    "El transport json2 no admet compromisos de pagament. "
    "Només factures (x_aqua_invoice) i pagaments (x_aqua_payment)."
)


def normalize_odoo_transport(value) -> str:
    transport = (value or TRANSPORT_FASTAPI).strip().lower()
    if transport not in (TRANSPORT_FASTAPI, TRANSPORT_JSON2):
        raise OdooApiError(
            f"ODOO_TRANSPORT desconegut: {value!r}. "
            f"Usa '{TRANSPORT_FASTAPI}' o '{TRANSPORT_JSON2}'."
        )
    return transport


def wrap_json2_vals(payload: dict) -> dict:
    """Embolcalla el JSON del contracte per al create natiu d'Odoo."""
    aqua_id = ""
    if isinstance(payload, dict) and payload.get("aqua_id") is not None:
        aqua_id = str(payload.get("aqua_id"))
    return {
        "vals_list": [
            {
                "x_aqua_id": aqua_id,
                "x_aqua_json": payload,
            }
        ]
    }


def json2_model_for_batch(endpoint: str, object_type: str = "") -> str:
    hint = f"{endpoint or ''} {object_type or ''}".lower()
    if "commitment" in hint:
        raise OdooApiError(JSON2_COMMITMENTS_UNSUPPORTED)
    if "payment" in hint:
        return JSON2_PAYMENT_MODEL
    return JSON2_INVOICE_MODEL


def ensure_commitments_supported(client) -> None:
    if getattr(client, "is_json2", False):
        raise OdooApiError(JSON2_COMMITMENTS_UNSUPPORTED)


def _odoo_id_from_create_response(payload):
    if isinstance(payload, list):
        return payload[0] if payload else None
    if isinstance(payload, dict):
        return payload.get("id")
    if isinstance(payload, int):
        return payload
    return None


class OdooClient:
    def __init__(self, base_url=None, api_key=None, timeout=None, transport=None):
        self.base_url = (base_url or settings.ODOO_BASE_URL or "").rstrip("/")
        self.api_key = api_key or getattr(settings, "ODOO_API_KEY", "")
        self.timeout = timeout or getattr(settings, "ODOO_TIMEOUT", 30)
        if transport is None:
            transport = getattr(settings, "ODOO_TRANSPORT", TRANSPORT_FASTAPI)
        self.transport = normalize_odoo_transport(transport)

    @property
    def is_json2(self) -> bool:
        return self.transport == TRANSPORT_JSON2

    def _get_headers(self):
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if not self.api_key:
            return headers
        if self.is_json2:
            headers["Authorization"] = f"Bearer {self.api_key}"
        else:
            headers["Aqua360-Api-Key"] = self.api_key
        return headers

    def _log_request(
        self,
        *,
        method,
        endpoint,
        request_payload,
        response_payload=None,
        status_code=None,
        success=False,
        error_message="",
        object_type="",
        object_id="",
    ):
        IntegrationRequestLog.objects.create(
            provider=PROVIDER,
            direction=IntegrationRequestLog.DIRECTION_OUTBOUND,
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

    def _parse_response_payload(self, response):
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    def _request(
        self,
        method,
        endpoint,
        *,
        payload=None,
        object_type="",
        object_id="",
        accept_statuses=None,
    ):
        """
        Request genèric (GET/POST).

        accept_statuses: codis HTTP tractats com a èxit (per defecte només 2xx via response.ok).
        Els lots retornen 202 (acceptat) o 200 (ja rebut); 422 rebutja el lot sencer.
        """
        if not self.base_url:
            raise OdooApiError("ODOO_BASE_URL no està configurat.")
        if not endpoint:
            raise OdooApiError("Endpoint Odoo no informat.")

        url = f"{self.base_url}{endpoint}"
        accept_statuses = set(accept_statuses or ())
        method = (method or "GET").upper()

        try:
            response = requests.request(
                method,
                url,
                json=payload if method != "GET" else None,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            error_message = f"Error connectant amb Odoo: {exc}"
            self._log_request(
                method=method,
                endpoint=endpoint,
                request_payload=payload,
                success=False,
                error_message=error_message,
                object_type=object_type,
                object_id=object_id,
            )
            raise OdooApiError(error_message) from exc

        response_payload = self._parse_response_payload(response)
        is_accepted = response.ok or response.status_code in accept_statuses

        if not is_accepted:
            error_message = (
                f"Error resposta Odoo {response.status_code}: {response.text}"
            )
            self._log_request(
                method=method,
                endpoint=endpoint,
                request_payload=payload,
                response_payload=response_payload,
                status_code=response.status_code,
                success=False,
                error_message=error_message,
                object_type=object_type,
                object_id=object_id,
            )
            raise OdooApiError(error_message)

        self._log_request(
            method=method,
            endpoint=endpoint,
            request_payload=payload,
            response_payload=response_payload,
            status_code=response.status_code,
            success=True,
            object_type=object_type,
            object_id=object_id,
        )
        return {
            "status_code": response.status_code,
            "payload": response_payload,
        }

    def _post(self, endpoint, payload, *, object_type="", object_id="", accept_statuses=None):
        return self._request(
            "POST",
            endpoint,
            payload=payload,
            object_type=object_type,
            object_id=object_id,
            accept_statuses=accept_statuses,
        )

    def _get(self, endpoint, *, object_type="", object_id="", accept_statuses=None):
        return self._request(
            "GET",
            endpoint,
            object_type=object_type,
            object_id=object_id,
            accept_statuses=accept_statuses,
        )

    def _push_document(self, payload: dict, *, endpoint: str, object_type: str):
        aqua_id = payload.get("aqua_id", "") if isinstance(payload, dict) else ""
        body = wrap_json2_vals(payload) if self.is_json2 else payload
        result = self._post(
            endpoint,
            body,
            object_type=object_type,
            object_id=str(aqua_id or ""),
        )
        return result["payload"]

    def push_invoice(self, payload: dict):
        endpoint = JSON2_INVOICE_ENDPOINT if self.is_json2 else INVOICES_ENDPOINT
        return self._push_document(payload, endpoint=endpoint, object_type="invoice")

    def push_payment(self, payload: dict):
        endpoint = JSON2_PAYMENT_ENDPOINT if self.is_json2 else PAYMENTS_ENDPOINT
        return self._push_document(
            payload, endpoint=endpoint, object_type="payment_movement"
        )

    def push_batch(self, endpoint: str, batch_id: str, items: list, *, object_type=""):
        """
        Envia un lot.

        fastapi: { "batch_id", "items" } a l'endpoint del SendBatchType.
        Accepta 202 (nou) i 200 (ja rebut).

        json2: un POST create per ítem. No s'atura al primer error.
        Retorna un resultat final (summary + results) perquè el lot es tanqui
        sense webhook.
        """
        if self.is_json2:
            return self._push_batch_json2(
                batch_id, items, endpoint=endpoint, object_type=object_type
            )

        payload = {"batch_id": batch_id, "items": items}
        return self._post(
            endpoint,
            payload,
            object_type=object_type or "send_batch",
            object_id=batch_id,
            accept_statuses={200, 202},
        )

    def _push_batch_json2(self, batch_id, items, *, endpoint, object_type):
        if not self.api_key:
            raise OdooApiError(
                "ODOO_API_KEY no està configurat per al transport json2."
            )
        model = json2_model_for_batch(endpoint, object_type)
        create_endpoint = f"/json/2/{model}/create"
        item_object_type = (
            "payment_movement" if model == JSON2_PAYMENT_MODEL else "invoice"
        )
        results = []
        ok = 0
        error = 0
        for item in items:
            aqua_id = ""
            if isinstance(item, dict) and item.get("aqua_id") is not None:
                aqua_id = str(item.get("aqua_id"))
            try:
                response = self._post(
                    create_endpoint,
                    wrap_json2_vals(item if isinstance(item, dict) else {}),
                    object_type=item_object_type,
                    object_id=aqua_id,
                )
                odoo_id = _odoo_id_from_create_response(response["payload"])
                if odoo_id is None:
                    raise OdooApiError("Odoo no ha retornat l'ID del document creat.")
                results.append(
                    {
                        "aqua_id": aqua_id,
                        "odoo_id": odoo_id,
                        "status": "ok",
                        "message": None,
                    }
                )
                ok += 1
            except OdooApiError as exc:
                results.append(
                    {
                        "aqua_id": aqua_id,
                        "odoo_id": None,
                        "status": "error",
                        "message": str(exc),
                    }
                )
                error += 1

        now = timezone.now().isoformat()
        return {
            "status_code": 200,
            "payload": {
                "batch_id": batch_id,
                "type": "payments" if model == JSON2_PAYMENT_MODEL else "invoices",
                "status": "done",
                "received_at": now,
                "finished_at": now,
                "summary": {
                    "total": len(items),
                    "ok": ok,
                    "duplicate_ignored": 0,
                    "error": error,
                    "pending": 0,
                },
                "results": results,
            },
        }

    def get_batch_status(self, batch_id: str):
        """
        Consulta l'estat d'un lot a Odoo: GET /batch/{batch_id}.
        Retorna {status_code, payload} (mateix JSON que l'inbound final).

        json2 no té aquesta consulta: el resultat es tanca en enviar.
        """
        if self.is_json2:
            raise OdooApiError(
                "El transport json2 no consulta l'estat del lot a Odoo. "
                "El resultat queda tancat en enviar."
            )
        endpoint = f"/batch/{batch_id}"
        return self._get(
            endpoint,
            object_type="send_batch",
            object_id=batch_id,
        )
