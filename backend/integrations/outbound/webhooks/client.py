"""Signa i envia un avís (POST) i en deixa constància a IntegrationRequestLog."""
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

import requests
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder

from integrations.models import IntegrationRequestLog

PROVIDER = "webhooks"
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


def deliver(event):
    """Fa el POST de l'avís. No toca l'estat de l'avís: ho fa qui el crida."""
    url = settings.WEBHOOKS_URL
    body = serialize_payload(event.payload)
    timestamp = str(int(time.time()))
    headers = build_headers(event.event_type, event.event_id, timestamp, body, settings.WEBHOOKS_SECRET)

    status_code = None
    response_text = ""
    try:
        response = requests.post(url, data=body, headers=headers, timeout=settings.WEBHOOKS_TIMEOUT)
        status_code = response.status_code
        response_text = (response.text or "")[:2000]
        success = 200 <= status_code < 300
        retryable = not success and (status_code >= 500 or status_code in RETRYABLE_STATUS)
        error = "" if success else f"HTTP {status_code}"
    except requests.RequestException as exc:
        success = False
        retryable = True
        error = f"{type(exc).__name__}: {exc}"[:1000]

    # El contingut de l'avís ja és a WebhookEvent: aquí només la referència
    IntegrationRequestLog.objects.create(
        provider=PROVIDER,
        direction=IntegrationRequestLog.DIRECTION_OUTBOUND,
        method="POST",
        endpoint=url[:255],
        request_payload={"event_id": str(event.event_id), "event_type": event.event_type},
        response_payload={"body": response_text} if response_text else None,
        status_code=status_code,
        success=success,
        error_message=error,
        object_type=event.event_type,
        object_id=str(event.event_id),
    )
    return DeliveryResult(success=success, retryable=retryable, status_code=status_code, error=error)
