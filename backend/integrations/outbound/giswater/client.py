import requests
import json
from django.conf import settings

from integrations.models import IntegrationRequestLog

from .auth import get_http_auth
from .exceptions import GiswaterApiError

PROVIDER = "giswater"
GET_LIST_ENDPOINT = "/basic/getlist"
GET_MINCUTS_ENDPOINT = "/om/mincuts"


class GiswaterClient:
    def __init__(self, base_url=None, token=None, timeout=None):
        self.base_url = (base_url or settings.GISWATER_BASE_URL).rstrip("/")
        self._token = token
        self.timeout = timeout or getattr(settings, "GISWATER_TIMEOUT", 30)

    def _resolve_request_auth(self):
        """
        Returns (headers, auth) for requests.

        Ordre:
        1. Token passat al constructor
        2. GISWATER_TOKEN (Bearer estàtic)
        3. Keycloak OAuth si GISWATER_KEYCLOAK_URL està definit
        4. HTTP Basic Auth (GISWATER_USERNAME / GISWATER_PASSWORD)
        """
        headers = {
            "Accept": "application/json",
        }

        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
            return headers, None

        static_token = getattr(settings, "GISWATER_TOKEN", None)
        if static_token:
            headers["Authorization"] = f"Bearer {static_token}"
            return headers, None

        auth_headers, auth = get_http_auth()
        headers.update(auth_headers)
        return headers, auth

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
        )
    
    def get_mincuts(self, schema: str):
        url = f"{self.base_url}{GET_MINCUTS_ENDPOINT}"
        params = { "schema": schema }
        headers, auth = self._resolve_request_auth()

        try:
            response = requests.get(
                url, params=params, headers=headers,
                auth=auth, timeout=self.timeout,
            )
        except requests.RequestException as exc:
            error_message = f"Error connectant amb Giswater: {exc}"
            self._log_request(
                method="GET",
                endpoint=GET_MINCUTS_ENDPOINT,
                request_payload=params,
                success=False,
                error_message=error_message,
            )
            raise GiswaterApiError(error_message) from exc

        if not response.ok:
            error_message = (
                f"Error resposta Giswater {response.status_code}: {response.text}"
            )
            self._log_request(
                method="GET",
                endpoint=GET_MINCUTS_ENDPOINT,
                request_payload=params,
                status_code=response.status_code,
                success=False,
                error_message=error_message,
            )
            raise GiswaterApiError(error_message)
        
        try:
            data = response.json()
        except ValueError as exc:
            error_message = "La resposta de Giswater no és JSON vàlid"
            self._log_request(
                method="GET",
                endpoint=GET_MINCUTS_ENDPOINT,
                request_payload=params,
                status_code=response.status_code,
                success=False,
                error_message=error_message,
            )
            raise GiswaterApiError(error_message) from exc

        self._log_request(
            method="GET",
            endpoint=GET_MINCUTS_ENDPOINT,
            request_payload=params,
            response_payload=data,
            status_code=response.status_code,
            success=True,
        )
        return data


    def get_list(self, schema: str, table_name: str, filter_fields: dict):
        url = f"{self.base_url}{GET_LIST_ENDPOINT}"
        params = {
            "schema": schema,
            "tableName": table_name,
        }

        if filter_fields is not None:
            params["filterFields"] = json.dumps(filter_fields)

        headers, auth = self._resolve_request_auth()

        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                auth=auth,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            error_message = f"Error connectant amb Giswater: {exc}"
            self._log_request(
                method="GET",
                endpoint=GET_LIST_ENDPOINT,
                request_payload=params,
                success=False,
                error_message=error_message,
            )
            raise GiswaterApiError(error_message) from exc

        if not response.ok:
            error_message = (
                f"Error resposta Giswater {response.status_code}: {response.text}"
            )
            self._log_request(
                method="GET",
                endpoint=GET_LIST_ENDPOINT,
                request_payload=params,
                status_code=response.status_code,
                success=False,
                error_message=error_message,
            )
            raise GiswaterApiError(error_message)

        try:
            data = response.json()
        except ValueError as exc:
            error_message = "La resposta de Giswater no és JSON vàlid"
            self._log_request(
                method="GET",
                endpoint=GET_LIST_ENDPOINT,
                request_payload=params,
                status_code=response.status_code,
                success=False,
                error_message=error_message,
            )
            raise GiswaterApiError(error_message) from exc

        self._log_request(
            method="GET",
            endpoint=GET_LIST_ENDPOINT,
            request_payload=params,
            response_payload=data,
            status_code=response.status_code,
            success=True,
        )
        return data
