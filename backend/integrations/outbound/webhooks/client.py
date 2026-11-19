"""Signa i envia un avís (POST) i en deixa constància a IntegrationRequestLog."""
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import requests
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction

from integrations.models import IntegrationRequestLog

logger = logging.getLogger(__name__)

PROVIDER = "webhooks"
RESPONSE_READ_LIMIT = 2000  # bytes de la resposta que es desen per al diagnòstic
RESPONSE_READ_SECONDS = 2  # temps màxim llegint-la (a més del timeout de cada lectura)
USER_AGENT = "aqua360-customers-webhooks/1.0"
# Respostes que poden anar bé més endavant: es reintenten
RETRYABLE_STATUS = {408, 429}


@dataclass
class DeliveryResult:
    success: bool
    retryable: bool
    status_code: int | None = None
    error: str = ""


def serialize_payload(payload):
    return json.dumps(payload, cls=DjangoJSONEncoder, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sign(secret, timestamp, body):
    """sha256=HMAC(secret, "<timestamp>.<body>"): el receptor ho recalcula amb el mateix secret."""
    message = f"{timestamp}.".encode("utf-8") + body
    return "sha256=" + hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def build_headers(event_type, event_id, timestamp, body, secret):
    headers = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "X-Aqua360-Event": event_type,
        "X-Aqua360-Event-Id": str(event_id),
        "X-Aqua360-Timestamp": timestamp,
    }
    if secret:
        headers["X-Aqua360-Signature"] = sign(secret, timestamp, body)
    return headers


def safe_url(url):
    """Només l'origen de la URL (esquema, host i port): per als logs i la sortida
    de les ordres. El camí, la query o l'usuari podrien portar un token."""
    parts = urlsplit(url or "")
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, "", "", ""))


def _read_limited(response, limit=RESPONSE_READ_LIMIT, deadline_seconds=RESPONSE_READ_SECONDS):
    """Llegeix com a molt `limit` bytes durant com a molt `deadline_seconds`: n'hi ha
    prou per al diagnòstic i un receptor lent no reté l'enviador. `read1` torna el
    que ja ha arribat (una sola lectura del socket), així el termini es comprova
    entre lectures i el temps total queda limitat a `deadline_seconds` més el
    timeout d'una lectura."""
    chunks = []
    size = 0
    deadline = time.monotonic() + deadline_seconds
    try:
        while size < limit and time.monotonic() < deadline:
            chunk = response.raw.read1(limit - size)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
    except Exception:
        pass
    finally:
        response.close()
    return b"".join(chunks)[:limit].decode("utf-8", errors="replace").replace("\x00", "")


def _log_request(event, url, status_code, success, error, response_text):
    """El registre no ha de fer perdre el resultat de l'enviament."""
    try:
        with transaction.atomic():
            # El contingut de l'avís ja és a WebhookEvent: aquí només la referència
            IntegrationRequestLog.objects.create(
                provider=PROVIDER,
                direction=IntegrationRequestLog.DIRECTION_OUTBOUND,
                method="POST",
                endpoint=safe_url(url)[:255],
                request_payload={"event_id": str(event.event_id), "event_type": event.event_type},
                response_payload={"body": response_text} if response_text else None,
                status_code=status_code,
                success=success,
                error_message=error,
                object_type=event.event_type,
                object_id=str(event.event_id),
            )
    except Exception:
        logger.exception("No s'ha pogut registrar l'enviament d'un webhook")


def deliver(event):
    """Fa el POST de l'avís. No toca l'estat de l'avís: ho fa qui el crida.

    Sense redireccions: un 3xx no és una entrega (requests convertiria el POST en
    un GET sense cos) i queda com a error definitiu.
    """
    url = settings.WEBHOOKS_URL
    body = serialize_payload(event.payload)
    timestamp = str(int(time.time()))
    headers = build_headers(event.event_type, event.event_id, timestamp, body, settings.WEBHOOKS_SECRET)

    status_code = None
    response_text = ""
    try:
        response = requests.post(
            url, data=body, headers=headers, timeout=settings.WEBHOOKS_TIMEOUT,
            allow_redirects=False, stream=True,
        )
        status_code = response.status_code
        success = 200 <= status_code < 300
        if success:
            # Entregat: el cos no cal per a res
            response.close()
        else:
            response_text = _read_limited(response)
        retryable = not success and (status_code >= 500 or status_code in RETRYABLE_STATUS)
        error = "" if success else f"HTTP {status_code}"
    except requests.RequestException as exc:
        success = False
        retryable = True
        # Només el tipus: el missatge pot portar la URL sencera
        error = type(exc).__name__

    _log_request(event, url, status_code, success, error, response_text)
    return DeliveryResult(success=success, retryable=retryable, status_code=status_code, error=error)
