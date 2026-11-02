import requests
from django.conf import settings

from integrations.models import IntegrationRequestLog

from .exceptions import OdooApiError

PROVIDER = "odoo"
INVOICES_ENDPOINT = "/invoices"
PAYMENTS_ENDPOINT = "/payments"


class OdooClient:
    def __init__(self, base_url=None, api_key=None, timeout=None):
        self.base_url = (base_url or settings.ODOO_BASE_URL).rstrip("/")
        self.api_key = api_key or getattr(settings, "ODOO_API_KEY", "")
        self.timeout = timeout or getattr(settings, "ODOO_TIMEOUT", 30)

    def _get_headers(self):
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.api_key:
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

    def push_invoice(self, payload: dict):
        result = self._post(
            INVOICES_ENDPOINT,
            payload,
            object_type="invoice",
            object_id=payload.get("aqua_id", ""),
        )
        return result["payload"]

    def push_payment(self, payload: dict):
        result = self._post(
            PAYMENTS_ENDPOINT,
            payload,
            object_type="payment_movement",
            object_id=payload.get("aqua_id", ""),
        )
        return result["payload"]

    def push_batch(self, endpoint: str, batch_id: str, items: list, *, object_type=""):
        """
        Envia un lot: { "batch_id": "...", "items": [ ... ] }.
        L'endpoint ve de SendBatchType.endpoint.

        Retorna {status_code, payload}. Accepta 202 (nou) i 200 (ja rebut).
        """
        payload = {"batch_id": batch_id, "items": items}
        return self._post(
            endpoint,
            payload,
            object_type=object_type or "send_batch",
            object_id=batch_id,
            accept_statuses={200, 202},
        )

    def get_batch_status(self, batch_id: str):
        """
        Consulta l'estat d'un lot a Odoo: GET /batch/{batch_id}.
        Retorna {status_code, payload} (mateix JSON que l'inbound final).
        """
        endpoint = f"/batch/{batch_id}"
        return self._get(
            endpoint,
            object_type="send_batch",
            object_id=batch_id,
        )
