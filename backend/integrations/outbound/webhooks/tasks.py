import datetime
import logging
import time
from contextlib import contextmanager

from celery import shared_task
from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from integrations.models import WebhookEvent

from .client import deliver
from .dispatcher import webhooks_configured

logger = logging.getLogger(__name__)

# Clau del bloqueig de PostgreSQL que garanteix un sol enviador alhora
SENDER_LOCK_KEY = 275500001


@contextmanager
def single_sender():
    """Només un enviador alhora encara que el worker executi diverses tasques en
    paral·lel: així el ritme (WEBHOOKS_SEND_INTERVAL) és el de tota la instal·lació.
    Qui no obté el bloqueig plega; l'enviador actiu o el beat ja recolliran els seus."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [SENDER_LOCK_KEY])
        acquired = cursor.fetchone()[0]
    try:
        yield acquired
    finally:
        if acquired:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [SENDER_LOCK_KEY])


def apply_result(event, result, now=None):
    """Actualitza l'avís segons el resultat de l'enviament (entregat, reintent o fallit)."""
    now = now or timezone.now()
    event.attempts += 1
    event.last_status_code = result.status_code
    event.last_error = result.error
    if result.success:
        event.status = WebhookEvent.STATUS_SENT
        event.sent_at = now
        event.next_attempt_at = None
    else:
        delays = settings.WEBHOOKS_RETRY_DELAYS
        if result.retryable and event.attempts <= len(delays):
            event.next_attempt_at = now + datetime.timedelta(seconds=delays[event.attempts - 1])
        else:
            # 4xx (excepte 408/429) o intents exhaurits: es reenvia a mà
            event.status = WebhookEvent.STATUS_FAILED
            event.next_attempt_at = None
    event.save(update_fields=[
        "attempts", "last_status_code", "last_error", "status", "sent_at", "next_attempt_at", "updated_at",
    ])


def send_next_pending():
    """Envia l'avís pendent més antic que toqui. Torna None si no n'hi ha cap.

    La fila queda bloquejada mentre s'envia (skip_locked): dos workers no
    envien mai el mateix avís alhora.
    """
    with transaction.atomic():
        event = (
            WebhookEvent.objects.select_for_update(skip_locked=True)
            .filter(status=WebhookEvent.STATUS_PENDING, next_attempt_at__lte=timezone.now())
            .order_by("next_attempt_at", "id")
            .first()
        )
        if event is None:
            return None
        result = deliver(event)
        apply_result(event, result)
        return result


def send_event(event_pk):
    """Envia ara mateix un avís pendent concret (ordre send_test_webhook)."""
    with transaction.atomic():
        event = (
            WebhookEvent.objects.select_for_update()
            .filter(pk=event_pk, status=WebhookEvent.STATUS_PENDING)
            .first()
        )
        if event is None:
            return None
        result = deliver(event)
        apply_result(event, result)
        return result


@shared_task
def send_pending_webhooks():
    """Envia els avisos pendents, a poc a poc per no saturar el receptor.

    L'encua cada avís nou en confirmar-se la transacció i el beat cada minut (per
    als reintents i els que s'hagin perdut). Si en queden després d'un lot, es
    torna a encuar en lloc d'ocupar el worker indefinidament.
    """
    if not webhooks_configured():
        return {"status": "skipped"}

    sent = failed = 0
    more_pending = False
    with single_sender() as acquired:
        if not acquired:
            return {"status": "busy"}
        for _ in range(settings.WEBHOOKS_SEND_BATCH):
            result = send_next_pending()
            if result is None:
                break
            if result.success:
                sent += 1
            else:
                failed += 1
            time.sleep(settings.WEBHOOKS_SEND_INTERVAL)
        else:
            more_pending = True

    # Encuat després d'alliberar el bloqueig perquè el pugui agafar
    if more_pending:
        send_pending_webhooks.delay()

    if failed:
        logger.warning("Webhooks: %s enviats, %s amb error", sent, failed)
    return {"status": "success", "sent": sent, "errors": failed}


@shared_task
def scan_invoice_status_webhooks():
    """Avisos d'estat de pagament de les factures (invoice.paid, invoice.returned,
    invoice.expired i invoice.cancelled): el beat la crida cada
    WEBHOOKS_INVOICE_SCAN_MINUTES. Vegeu invoice_status.py."""
    from .invoice_status import scan

    return scan()
