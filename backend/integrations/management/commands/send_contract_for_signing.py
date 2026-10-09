from django.core.management.base import BaseCommand, CommandError

from contract.models import Contract
from integrations.outbound.signing.exceptions import SigningApiError
from integrations.outbound.signing.services import create_contract_signing_session


def _resolve_contract(ref):
    ref = (ref or "").strip()
    if not ref:
        return None
    contract = Contract.objects.filter(token=ref).first()
    if contract:
        return contract
    if ref.isdigit():
        return Contract.objects.filter(id=int(ref)).first()
    return None


class Command(BaseCommand):
    help = (
        "Genera el PDF del contracte i l'envia a Aqua360 Sign per a la signatura digital del client."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--contract",
            required=True,
            help="ID o token del contracte.",
        )
        parser.add_argument(
            "--recipient-name",
            dest="recipient_name",
            default="",
            help="Nom del signant (opcional; per defecte el titular del contracte).",
        )
        parser.add_argument(
            "--recipient-email",
            dest="recipient_email",
            default="",
            help="Correu del signant (opcional; per defecte el contacte del contracte).",
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
            help="Permet enviar a signar encara que el contracte ja tingui contract_file.",
        )

    def handle(self, *args, **options):
        contract = _resolve_contract(options["contract"])
        if not contract:
            raise CommandError(
                f"No s'ha trobat cap contracte amb id/token '{options['contract']}'"
            )

        try:
            result = create_contract_signing_session(
                contract,
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
                f"Sessió de signatura creada per al contracte {result['contract_token']} "
                f"(id={result['contract_id']})"
            )
        )
        self.stdout.write(f"  session_id:   {result['session_id']}")
        self.stdout.write(f"  status:       {result['status']}")
        self.stdout.write(f"  email_sent:   {result['email_sent']}")
        if result.get("expires_at"):
            self.stdout.write(f"  expires_at:   {result['expires_at']}")
        if result.get("signing_url"):
            self.stdout.write(f"  signing_url:  {result['signing_url']}")
