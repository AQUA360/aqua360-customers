import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from integrations.models import WebhookEvent
from integrations.outbound.webhooks.dispatcher import schedule_send, webhooks_configured


class Command(BaseCommand):
    help = (
        "Torna a posar a la cua d'enviament els avisos (webhooks) fallits o desats "
        "mentre no hi havia URL (disabled)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--status", choices=[WebhookEvent.STATUS_FAILED, WebhookEvent.STATUS_DISABLED],
                            default=WebhookEvent.STATUS_FAILED, help="Estat dels avisos a reenviar (per defecte, failed).")
        parser.add_argument("--type", dest="event_type", help="Només aquest tipus d'avís (p. ex. invoice.issued).")
        parser.add_argument("--since", help="Només els creats a partir d'aquest dia (AAAA-MM-DD).")
        parser.add_argument("--dry-run", action="store_true", help="Només diu quants n'hi ha.")

    def handle(self, *args, **options):
        events = WebhookEvent.objects.filter(status=options["status"])
        if options["event_type"]:
            events = events.filter(event_type=options["event_type"])
        if options["since"]:
            try:
                since = datetime.date.fromisoformat(options["since"])
            except ValueError:
                raise CommandError("--since ha de ser una data AAAA-MM-DD.")
            events = events.filter(created_at__date__gte=since)

        total = events.count()
        if options["dry_run"]:
            self.stdout.write(f"{total} avisos a reenviar.")
            return
        if not webhooks_configured():
            raise CommandError(
                "Els webhooks no estan activats o els falta la URL o el secret "
                "(WEBHOOKS_ENABLED, WEBHOOKS_URL, WEBHOOKS_SECRET)."
            )

        updated = events.update(
            status=WebhookEvent.STATUS_PENDING, attempts=0, next_attempt_at=timezone.now(), last_error="",
        )
        if updated:
            schedule_send()
        self.stdout.write(self.style.SUCCESS(f"{updated} avisos tornen a ser pendents d'enviament."))
