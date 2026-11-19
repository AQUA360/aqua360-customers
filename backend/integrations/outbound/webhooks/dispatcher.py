"""Desa els avisos de sortida a la bústia (WebhookEvent) i n'encua l'enviament."""
import logging
import uuid

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from integrations.models import WebhookEvent

logger = logging.getLogger(__name__)

PAYLOAD_VERSION = "1.0"
SOURCE_SYSTEM = "aqua360-customers"


def webhooks_enabled():
    return bool(getattr(settings, "WEBHOOKS_ENABLED", False))


def webhooks_configured():
    """Activat, amb URL i amb secret: els avisos es poden enviar. Sense secret no
    s'envien sense signar: es desen com a "disabled" i es poden reenviar després."""
    return (
        webhooks_enabled()
        and bool(getattr(settings, "WEBHOOKS_URL", ""))
        and bool(getattr(settings, "WEBHOOKS_SECRET", ""))
    )


def build_envelope(event_id, event_type, occurred_at, data):
    return {
        "event_id": str(event_id),
        "event_type": event_type,
        "occurred_at": occurred_at.isoformat(),
        "version": PAYLOAD_VERSION,
        "source": {
            "system": SOURCE_SYSTEM,
            "instance": getattr(settings, "INSTANCE_UID", "") or None,
        },
        "data": data,
    }


def schedule_send():
    """Encua la tasca d'enviament. Si el broker no respon, el beat la recollirà."""
    from .tasks import send_pending_webhooks

    try:
        send_pending_webhooks.delay()
    except Exception:
        logger.exception("No s'ha pogut encuar l'enviament dels webhooks")


def emit(event_type, object_type, object_id, build_data, dedupe_key=None, schedule=True):
    """Desa un avís a la bústia. Es crida des del codi de negoci.

    `build_data` és una funció que torna el diccionari `data`: només es crida si el
    mòdul està activat, així les instal·lacions sense webhooks no fan cap consulta.
    `dedupe_key` evita desar dues vegades el mateix fet; sense, l'avís és únic.

    Mai fa fallar l'acció de negoci: tot va dins un savepoint i els errors només es
    registren al log. L'enviament s'encua quan la transacció es confirma; si es
    desfà, l'avís desapareix amb ella.
    """
    if not webhooks_enabled():
        return None

    configured = webhooks_configured()
    if not configured and getattr(settings, "WEBHOOKS_URL", "") and not getattr(settings, "WEBHOOKS_SECRET", ""):
        logger.warning("Webhooks amb URL però sense WEBHOOKS_SECRET: l'avís es desa com a disabled i no s'envia")
    event_id = uuid.uuid4()
    now = timezone.now()
    key = dedupe_key or f"{event_type}:{event_id}"
    # Sense dades de l'objecte als logs: poden ser personals
    if dedupe_key and WebhookEvent.objects.filter(dedupe_key=key).exists():
        logger.info("Webhook ja desat: no es repeteix")
        return None

    try:
        with transaction.atomic():
            payload = build_envelope(event_id, event_type, now, build_data())
    except Exception:
        logger.exception("No s'han pogut construir les dades d'un webhook")
        return None

    try:
        with transaction.atomic():
            event = WebhookEvent.objects.create(
                event_id=event_id,
                event_type=event_type,
                object_type=object_type,
                object_id=str(object_id),
                dedupe_key=key,
                payload=payload,
                status=WebhookEvent.STATUS_PENDING if configured else WebhookEvent.STATUS_DISABLED,
                next_attempt_at=now if configured else None,
            )
    except IntegrityError:
        # Només és un duplicat si la clau ja hi és (p. ex. dues peticions alhora)
        if WebhookEvent.objects.filter(dedupe_key=key).exists():
            logger.info("Webhook ja desat: no es repeteix")
        else:
            logger.exception("No s'ha pogut desar un webhook")
        return None
    except Exception:
        logger.exception("No s'ha pogut desar un webhook")
        return None

    if configured and schedule:
        transaction.on_commit(schedule_send)
    return event
