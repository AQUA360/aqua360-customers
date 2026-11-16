import requests
from django.conf import settings

from integrations.models import IntegrationRequestLog

from .exceptions import OVApiError

PROVIDER = "ov"


class OVClient:
    """Client de l'API de l'oficina virtual (crides del Customers cap a l'OV)."""

    def __init__(self, base_url=None, api_key=None, timeout=None):
        self.base_url = (base_url or settings.OV_API_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.OV_API_KEY
        self.timeout = timeout or settings.OV_API_TIMEOUT

    def _headers(self):
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Token {self.api_key}"
        return headers

    def _log_request(self, *, endpoint, response_payload=None, status_code=None, success=False, error_message=""):
        IntegrationRequestLog.objects.create(
            provider=PROVIDER,
            direction=IntegrationRequestLog.DIRECTION_OUTBOUND,
            method="GET",
            endpoint=endpoint,
            response_payload=response_payload,
            status_code=status_code,
            success=success,
            error_message=error_message,
        )

    def get_active_contracts(self):
        """Contractes que tenen l'oficina virtual activa (resposta JSON tal com arriba)."""
        endpoint = settings.OV_ACTIVE_CONTRACTS_ENDPOINT
        try:
            response = requests.get(f"{self.base_url}{endpoint}", headers=self._headers(), timeout=self.timeout)
        except requests.RequestException as exc:
            error_message = f"Error connectant amb l'oficina virtual: {exc}"
            self._log_request(endpoint=endpoint, error_message=error_message)
            raise OVApiError(error_message) from exc

        if not response.ok:
            error_message = f"Error resposta de l'oficina virtual {response.status_code}: {response.text[:2000]}"
            self._log_request(endpoint=endpoint, status_code=response.status_code, error_message=error_message)
            raise OVApiError(error_message)

        try:
            data = response.json()
        except ValueError as exc:
            error_message = "La resposta de l'oficina virtual no és JSON vàlid"
            self._log_request(endpoint=endpoint, status_code=response.status_code, error_message=error_message)
            raise OVApiError(error_message) from exc

        # La llista porta correus d'usuaris i es demana cada dia: al registre només el recompte.
        count = len(data) if isinstance(data, list) else None
        self._log_request(
            endpoint=endpoint,
            response_payload={"count": count},
            status_code=response.status_code,
            success=True,
        )
        return data
