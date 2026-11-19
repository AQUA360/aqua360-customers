from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from integrations.models import WebhookEvent
from integrations.outbound.webhooks.client import safe_url
from integrations.outbound.webhooks.dispatcher import emit, schedule_send, webhooks_configured
from integrations.outbound.webhooks.tasks import send_event, single_sender

TEST_EVENT = "webhook.test"


class Command(BaseCommand):
    help = (
        "Envia un avís de prova (webhook.test) a WEBHOOKS_URL i mostra la resposta. "
        "Serveix per comprovar la URL i la signatura amb el receptor."
    )

    def handle(self, *args, **options):
        if not webhooks_configured():
            raise CommandError(
                "Els webhooks no estan activats o els falta la URL o el secret "
                "(WEBHOOKS_ENABLED, WEBHOOKS_URL, WEBHOOKS_SECRET)."
            )

        event = emit(TEST_EVENT, "test", "", lambda: {"message": "Avís de prova del Customers"}, schedule=False)
        if event is None:
            raise CommandError("No s'ha pogut desar l'avís de prova: mira el log.")

        self.stdout.write(f"URL:      {safe_url(settings.WEBHOOKS_URL)}")
        self.stdout.write(f"Event id: {event.event_id}")

        # Pel mateix enviador únic que el worker: mai dos POST alhora al receptor
        with single_sender() as acquired:
            if acquired:
                send_event(event.pk)
        if not acquired:
            schedule_send()
            # No s'ha pogut confirmar l'entrega: per als scripts, és un error
            raise CommandError(
                "L'enviador està ocupat: l'avís de prova queda pendent i s'enviarà en breu. "
                "Comprova'n l'estat a l'admin o torna-ho a provar."
            )

        # Només compta l'estat final (el pot haver enviat el worker mateix)
        event.refresh_from_db()
        if event.status == WebhookEvent.STATUS_SENT:
            self.stdout.write(self.style.SUCCESS(f"Entregat (HTTP {event.last_status_code})."))
            return
        raise CommandError(f"No entregat: {event.last_error or 'sense resposta'} (estat {event.status}).")
