from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from integrations.models import WebhookEvent
from integrations.outbound.webhooks.dispatcher import emit, webhooks_configured
from integrations.outbound.webhooks.tasks import send_event

TEST_EVENT = "webhook.test"


class Command(BaseCommand):
    help = (
        "Envia un avís de prova (webhook.test) a WEBHOOKS_URL i mostra la resposta. "
        "Serveix per comprovar la URL i la signatura amb el receptor."
    )

    def handle(self, *args, **options):
        if not webhooks_configured():
            raise CommandError("Els webhooks no estan activats o no tenen URL (WEBHOOKS_ENABLED, WEBHOOKS_URL).")

        event = emit(TEST_EVENT, "test", "", lambda: {"message": "Avís de prova del Customers"}, schedule=False)
        if event is None:
            raise CommandError("No s'ha pogut desar l'avís de prova: mira el log.")

        self.stdout.write(f"URL:      {settings.WEBHOOKS_URL}")
        self.stdout.write(f"Signatura: {'sí' if settings.WEBHOOKS_SECRET else 'no (WEBHOOKS_SECRET buit)'}")
        self.stdout.write(f"Event id: {event.event_id}")

        result = send_event(event.pk)
        event.refresh_from_db()
        if result and event.status == WebhookEvent.STATUS_SENT:
            self.stdout.write(self.style.SUCCESS(f"Entregat (HTTP {event.last_status_code})."))
        else:
            self.stdout.write(self.style.ERROR(f"No entregat: {event.last_error or 'sense resposta'} (estat {event.status})."))
