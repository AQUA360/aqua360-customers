import json

import requests
from django.conf import settings

from integrations.models import IntegrationRequestLog

from .exceptions import SigningApiError

PROVIDER = "signing"
CREATE_SESSION_ENDPOINT = "/api/sessions/"
SESSION_ENDPOINT_TEMPLATE = "/api/sessions/{session_id}/"
SIGNED_DOCUMENT_ENDPOINT_TEMPLATE = "/api/sessions/{session_id}/documents/{document_id}/signed/"
# UUID nul: Sign autentica la clau i respon 404 perquè la sessió no existeix.
# No crea cap sessió ni envia cap correu.
PROBE_SESSION_ID = "00000000-0000-0000-0000-000000000000"


def _json_body(response):
    content_type = ""
    headers = getattr(response, "headers", None)
    if headers is not None:
        content_type = headers.get("Content-Type", "") or ""
    if "json" not in content_type.lower():
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


class SigningClient:
    def __init__(self, base_url=None, api_key=None, timeout=None):
        self.base_url = (base_url or settings.SIGNING_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.SIGNING_API_KEY
        self.timeout = timeout or getattr(settings, "SIGNING_TIMEOUT", 30)

    def _get_headers(self):
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
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

    def create_session(
        self,
        *,
        recipient_name,
        recipient_email,
        documents,
        recipient_phone=None,
        external_reference=None,
        callback_url=None,
        document_metadata=None,
        object_type="",
        object_id="",
    ):
        """
        Crea una sessió de signatura a Aqua360 Sign.

        `documents`: llista de tuples (filename, bytes, content_type).
        """
        url = f"{self.base_url}{CREATE_SESSION_ENDPOINT}"
        data = {
            "recipient_name": recipient_name,
            "recipient_email": recipient_email,
        }
        if recipient_phone:
            data["recipient_phone"] = recipient_phone
        if external_reference:
            data["external_reference"] = external_reference
        if callback_url:
            data["callback_url"] = callback_url
        if document_metadata is not None:
            data["document_metadata"] = json.dumps(document_metadata)

        files = [
            ("documents", (filename, content, content_type or "application/pdf"))
            for filename, content, content_type in documents
        ]

        log_payload = {
            **data,
            "documents": [filename for filename, _, _ in documents],
        }

        try:
            response = requests.post(
                url,
                data=data,
                files=files,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            error_message = f"Error connectant amb Aqua360 Sign: {exc}"
            self._log_request(
                method="POST",
                endpoint=CREATE_SESSION_ENDPOINT,
                request_payload=log_payload,
                success=False,
                error_message=error_message,
                object_type=object_type,
                object_id=object_id,
            )
            raise SigningApiError(error_message) from exc

        if not response.ok:
            error_message = (
                f"Error resposta Aqua360 Sign {response.status_code}: {response.text}"
            )
            self._log_request(
                method="POST",
                endpoint=CREATE_SESSION_ENDPOINT,
                request_payload=log_payload,
                status_code=response.status_code,
                success=False,
                error_message=error_message,
                object_type=object_type,
                object_id=object_id,
            )
            raise SigningApiError(error_message)

        try:
            result = response.json()
        except ValueError as exc:
            error_message = "La resposta d'Aqua360 Sign no és JSON vàlid"
            self._log_request(
                method="POST",
                endpoint=CREATE_SESSION_ENDPOINT,
                request_payload=log_payload,
                status_code=response.status_code,
                success=False,
                error_message=error_message,
                object_type=object_type,
                object_id=object_id,
            )
            raise SigningApiError(error_message) from exc

        self._log_request(
            method="POST",
            endpoint=CREATE_SESSION_ENDPOINT,
            request_payload=log_payload,
            response_payload=result,
            status_code=response.status_code,
            success=True,
            object_type=object_type,
            object_id=object_id,
        )
        return result

    def check_connection(self):
        """
        Comprova que Aqua360 Sign respon i que l'API key és vàlida.

        Fa GET d'una sessió que no existeix. Un 404 JSON vol dir que la clau
        ha passat l'autenticació. Un 403 vol dir que Sign l'ha rebutjat.
        No crea cap sessió ni envia cap correu.
        """
        if not self.base_url:
            raise SigningApiError("SIGNING_BASE_URL no està configurat")
        if not self.api_key:
            raise SigningApiError("SIGNING_API_KEY no està configurat")

        endpoint = SESSION_ENDPOINT_TEMPLATE.format(session_id=PROBE_SESSION_ID)
        url = f"{self.base_url}{endpoint}"
        request_payload = {"probe": True, "session_id": PROBE_SESSION_ID}

        try:
            response = requests.get(url, headers=self._get_headers(), timeout=self.timeout)
        except requests.RequestException as exc:
            error_message = f"Error connectant amb Aqua360 Sign: {exc}"
            self._log_request(
                method="GET",
                endpoint=endpoint,
                request_payload=request_payload,
                success=False,
                error_message=error_message,
                object_type="connection_check",
            )
            raise SigningApiError(error_message) from exc

        body = _json_body(response)
        if response.status_code == 404 and body is not None:
            self._log_request(
                method="GET",
                endpoint=endpoint,
                request_payload=request_payload,
                response_payload=body,
                status_code=response.status_code,
                success=True,
                object_type="connection_check",
            )
            return {
                "ok": True,
                "status_code": response.status_code,
                "base_url": self.base_url,
            }

        if response.status_code in (401, 403):
            detail = (body or {}).get("detail") if body else ""
            error_message = "Aqua360 Sign ha rebutjat l'API key"
            if detail:
                error_message = f"{error_message}: {detail}"
            self._log_request(
                method="GET",
                endpoint=endpoint,
                request_payload=request_payload,
                response_payload=body,
                status_code=response.status_code,
                success=False,
                error_message=error_message,
                object_type="connection_check",
            )
            raise SigningApiError(error_message)

        snippet = (response.text or "")[:300]
        error_message = (
            f"Resposta inesperada d'Aqua360 Sign {response.status_code}: {snippet}"
        )
        self._log_request(
            method="GET",
            endpoint=endpoint,
            request_payload=request_payload,
            response_payload=body,
            status_code=response.status_code,
            success=False,
            error_message=error_message,
            object_type="connection_check",
        )
        raise SigningApiError(error_message)

    def download_signed_document(self, session_id, document_id, *, object_type="", object_id=""):
        """
        Descarrega el PDF firmat (amb marca SES) d'un document d'una sessió
        d'Aqua360 Sign: GET /api/sessions/<session_id>/documents/<document_id>/signed/
        """
        endpoint = SIGNED_DOCUMENT_ENDPOINT_TEMPLATE.format(
            session_id=session_id, document_id=document_id
        )
        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.get(url, headers=self._get_headers(), timeout=self.timeout)
        except requests.RequestException as exc:
            error_message = f"Error connectant amb Aqua360 Sign: {exc}"
            self._log_request(
                method="GET",
                endpoint=endpoint,
                request_payload={"session_id": session_id, "document_id": document_id},
                success=False,
                error_message=error_message,
                object_type=object_type,
                object_id=object_id,
            )
            raise SigningApiError(error_message) from exc

        if not response.ok:
            error_message = (
                f"Error resposta Aqua360 Sign {response.status_code}: {response.text}"
            )
            self._log_request(
                method="GET",
                endpoint=endpoint,
                request_payload={"session_id": session_id, "document_id": document_id},
                status_code=response.status_code,
                success=False,
                error_message=error_message,
                object_type=object_type,
                object_id=object_id,
            )
            raise SigningApiError(error_message)

        self._log_request(
            method="GET",
            endpoint=endpoint,
            request_payload={"session_id": session_id, "document_id": document_id},
            status_code=response.status_code,
            success=True,
            object_type=object_type,
            object_id=object_id,
        )
        return response.content

    def get_session(self, session_id, *, object_type="", object_id="", log_success=False):
        """
        Consulta l'estat d'una sessió d'Aqua360 Sign:
        GET /api/sessions/<session_id>/

        `log_success=False` per defecte perquè això ho crida el sondeig periòdic
        (`poll_signing_sessions`) i registrar cada consulta ompliria
        `IntegrationRequestLog` de soroll; els errors sí que es registren sempre.
        """
        endpoint = SESSION_ENDPOINT_TEMPLATE.format(session_id=session_id)
        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.get(url, headers=self._get_headers(), timeout=self.timeout)
        except requests.RequestException as exc:
            error_message = f"Error connectant amb Aqua360 Sign: {exc}"
            self._log_request(
                method="GET",
                endpoint=endpoint,
                request_payload={"session_id": session_id},
                success=False,
                error_message=error_message,
                object_type=object_type,
                object_id=object_id,
            )
            raise SigningApiError(error_message) from exc

        if not response.ok:
            error_message = (
                f"Error resposta Aqua360 Sign {response.status_code}: {response.text}"
            )
            self._log_request(
                method="GET",
                endpoint=endpoint,
                request_payload={"session_id": session_id},
                status_code=response.status_code,
                success=False,
                error_message=error_message,
                object_type=object_type,
                object_id=object_id,
            )
            raise SigningApiError(error_message)

        try:
            result = response.json()
        except ValueError as exc:
            error_message = "La resposta d'Aqua360 Sign no és JSON vàlid"
            self._log_request(
                method="GET",
                endpoint=endpoint,
                request_payload={"session_id": session_id},
                status_code=response.status_code,
                success=False,
                error_message=error_message,
                object_type=object_type,
                object_id=object_id,
            )
            raise SigningApiError(error_message) from exc

        if log_success:
            self._log_request(
                method="GET",
                endpoint=endpoint,
                request_payload={"session_id": session_id},
                response_payload=result,
                status_code=response.status_code,
                success=True,
                object_type=object_type,
                object_id=object_id,
            )
        return result
