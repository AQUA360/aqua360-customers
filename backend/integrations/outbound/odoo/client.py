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

    def _post(self, endpoint, payload, *, object_type="", object_id=""):
        if not self.base_url:
            raise OdooApiError("ODOO_BASE_URL no està configurat.")

        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            error_message = f"Error connectant amb Odoo: {exc}"
            self._log_request(
                method="POST",
                endpoint=endpoint,
                request_payload=payload,
                success=False,
                error_message=error_message,
                object_type=object_type,
                object_id=object_id,
            )
            raise OdooApiError(error_message) from exc

        try:
            response_payload = response.json()
        except ValueError:
            response_payload = {"raw": response.text}

        if not response.ok:
            error_message = (
                f"Error resposta Odoo {response.status_code}: {response.text}"
            )
            self._log_request(
                method="POST",
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
            method="POST",
            endpoint=endpoint,
            request_payload=payload,
            response_payload=response_payload,
            status_code=response.status_code,
            success=True,
            object_type=object_type,
            object_id=object_id,
        )
        return response_payload

    def push_invoice(self, payload: dict):
        return self._post(
            INVOICES_ENDPOINT,
            payload,
            object_type="invoice",
            object_id=payload.get("aqua_id", ""),
        )

    def push_payment(self, payload: dict):
        return self._post(
            PAYMENTS_ENDPOINT,
            payload,
            object_type="payment_movement",
            object_id=payload.get("aqua_id", ""),
        )
