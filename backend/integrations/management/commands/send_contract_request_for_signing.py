from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from contract.models import ContractRequest
from integrations.outbound.signing.exceptions import SigningApiError
from integrations.outbound.signing.services import create_contract_request_signing_session


class Command(BaseCommand):
    help = (
        "Genera el PDF d'una sol·licitud de contracte i l'envia a Aqua360 Sign "
        "per a la signatura digital del client."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--contract-request-id",
            type=int,
            required=True,
            help="ID de la sol·licitud de contracte (ContractRequest).",
        )
        parser.add_argument(
            "--recipient-name",
            dest="recipient_name",
            default="",
            help="Nom del signant (opcional; per defecte el titular).",
        )
        parser.add_argument(
            "--recipient-email",
            dest="recipient_email",
            default="",
            help="Correu del signant (opcional).",
        )
        parser.add_argument(
            "--recipient-phone",
            dest="recipient_phone",
            default="",
            help="Telèfon del signant (opcional).",
        )
        parser.add_argument(
            "--callback-url",
            dest="callback_url",
            default="",
            help="URL del webhook (opcional; per defecte SIGNING_CALLBACK_URL).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Permet enviar a signar encara que ja tingui contract_file.",
        )

    def handle(self, *args, **options):
        contract_request_id = options["contract_request_id"]
        try:
            contract_request = ContractRequest.objects.get(id=contract_request_id)
        except ContractRequest.DoesNotExist:
            db = settings.DATABASES["default"]
            raise CommandError(
                f"No s'ha trobat cap ContractRequest amb id={contract_request_id} "
                f"a la base de dades '{db['NAME']}' ({db['HOST']}:{db['PORT']}). "
                "Comprova que DATABASE_NAME al .env coincideix amb la del servidor en execució."
            ) from None

        try:
            result = create_contract_request_signing_session(
                contract_request,
                recipient_name=options["recipient_name"] or None,
                recipient_email=options["recipient_email"] or None,
                recipient_phone=options["recipient_phone"] or None,
                callback_url=options["callback_url"] or None,
                force=options["force"],
            )
        except SigningApiError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Sessió de signatura creada per a la sol·licitud "
                f"{result['contract_request_token']} (id={result['contract_request_id']})"
            )
        )
        self.stdout.write(f"  session_id:   {result['session_id']}")
        self.stdout.write(f"  status:       {result['status']}")
        self.stdout.write(f"  email_sent:   {result['email_sent']}")
        if result.get("expires_at"):
            self.stdout.write(f"  expires_at:   {result['expires_at']}")
        if result.get("signing_url"):
            self.stdout.write(f"  signing_url:  {result['signing_url']}")
