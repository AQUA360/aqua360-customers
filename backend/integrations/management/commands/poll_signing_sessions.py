from django.core.management.base import BaseCommand

from integrations.outbound.signing.polling import poll_signing_sessions


class Command(BaseCommand):
    help = (
        "Consulta a Aqua360 Sign les sessions de signatura encara obertes i, per a les que "
        "ja estan firmades, es baixa el PDF segellat i el desa. Fa la mateixa feina que el "
        "webhook `session.signed`, però només amb trànsit de sortida: serveix per a les "
        "instal·lacions on Sign no pot arribar al backend, i per recuperar callbacks perduts."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--document-sign",
            dest="document_signs",
            action="append",
            default=[],
            help=(
                "ID d'un DocumentSign concret (es pot repetir). Per defecte, tots els que "
                "estan en estat SENDED."
            ),
        )
        parser.add_argument(
            "--session",
            dest="sessions",
            action="append",
            default=[],
            help=(
                "ID de sessió d'una ContractSigningSession concreta (es pot repetir). Per "
                "defecte, totes les que estan en estat pending."
            ),
        )
        parser.add_argument(
            "--skip-contract-requests",
            action="store_true",
            help="Només sondeja els DocumentSign, no les sessions de ContractRequest.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Nombre màxim de sessions a consultar de cada tipus.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Informa del que faria sense desar res.",
        )

    def handle(self, *args, **options):
        document_sign_ids = [int(value) for value in options["document_signs"]]

        result = poll_signing_sessions(
            document_sign_ids=document_sign_ids or None,
            session_ids=options["sessions"] or None,
            dry_run=options["dry_run"],
            limit=options["limit"],
            include_contract_requests=not options["skip_contract_requests"],
        )

        if result["status"] == "skipped":
            self.stdout.write(self.style.WARNING(result["message"]))
            return

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Simulació (--dry-run): no s'ha desat res."))

        for entry in result["results"]:
            reference = (
                f"DocumentSign {entry['document_sign_id']}"
                if "document_sign_id" in entry
                else f"Sessió {entry['session_id']}"
            )
            line = f"{reference}: {entry['action']}"
            if entry.get("detail"):
                line += f" ({entry['detail']})"

            if entry["action"] in ("signed", "would_sign"):
                self.stdout.write(self.style.SUCCESS(line))
            elif entry["action"] == "error":
                self.stdout.write(self.style.ERROR(line))
            else:
                self.stdout.write(line)

        if not result["results"]:
            self.stdout.write("No hi ha cap sessió de signatura oberta.")
            return

        self.stdout.write("")
        self.stdout.write(
            "Resum: "
            + ", ".join(f"{action}={count}" for action, count in sorted(result["summary"].items()))
        )
