from django.core.management.base import BaseCommand

from integrations.outbound.webhooks.invoice_status import reset_state


class Command(BaseCommand):
    help = (
        "Refà la foto de l'estat de les factures dels avisos d'estat de pagament sense "
        "avisar de res. Feu-la servir després d'un temps amb els webhooks desactivats, "
        "per no avisar de tots els canvis acumulats."
    )

    def handle(self, *args, **options):
        total = reset_state()
        self.stdout.write(self.style.SUCCESS(f"Foto refeta: {total} factures"))
