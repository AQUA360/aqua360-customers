"""
Repara processos de comunicació creats sense Message (subjecte/cos) associats -- el bug
corregit a regenerate_missing_communications.py (aquest command feia servir la mateixa
lògica manualment i s'oblidava de generar els Message des del MessageTemplate).

Sense Message al procés, send_electronic_mail() no pot obtenir subjecte/cos i llança una
excepció DoesNotExist que el bucle de send_communications_task ignora silenciosament: la
comunicació es queda en estat "Pendent" per sempre i mai s'arriba a enviar ni a marcar com
a rebutjada.

Aquest command:
  1. Genera els Message que falten al procés a partir del seu MessageTemplate (`template`).
  2. Reassigna `comm.messages` a les comunicacions del procés que es van quedar sense
     missatge (mateixa lògica que create_comm_from_persons: un Message per MessageType
     segons el(s) type_tokens de cada comunicació).

No envia res: només repara les dades perquè el següent enviament (manual o programat)
pugui trobar subjecte/cos i seguir el seu curs normal (enviar-se, o quedar Rebutjada amb
un motiu clar si torna a fallar per una altra causa).

Ús:
  # 1) Comprovar què es faria, sense escriure res:
  python manage.py backfill_process_messages 170 --dry-run

  # 2) Aplicar-ho de veritat:
  python manage.py backfill_process_messages 170 --commit
"""
from django.core.management.base import BaseCommand, CommandError

from communication.models import CommunicationProcess, Message, MessageType
from coredata.utils.name_utils import generate_token


class Command(BaseCommand):
    help = (
        "Genera els Message que falten a un CommunicationProcess (a partir del seu "
        "MessageTemplate) i reassigna comm.messages a les comunicacions afectades."
    )

    def add_arguments(self, parser):
        parser.add_argument("process_id", type=int)
        parser.add_argument("--commit", action="store_true",
                             help="Sense aquest flag NOMÉS es mostra el que es faria (dry-run per defecte).")

    def handle(self, *args, **options):
        process_id = options["process_id"]
        commit = options["commit"]

        try:
            process = CommunicationProcess.objects.get(id=process_id)
        except CommunicationProcess.DoesNotExist:
            raise CommandError(f"CommunicationProcess {process_id} no existeix.")

        if process.messages.exists():
            self.stdout.write(self.style.WARNING(
                f"Process {process_id} ja té {process.messages.count()} Message(s) associats. "
                f"No es toca res."
            ))
            return

        if not process.template:
            raise CommandError(
                f"Process {process_id} no té template associat: cal crear els Message manualment."
            )

        template_types = list(process.template.templates.select_related("type").all())
        if not template_types:
            raise CommandError(
                f"El template '{process.template}' (id={process.template_id}) no té cap "
                f"MessageTypeTemplate associat."
            )

        self.stdout.write(
            f"Process {process_id} (template='{process.template}'): es generaran "
            f"{len(template_types)} Message: {[t.type.token for t in template_types]}"
        )

        affected_comms = process.communications.filter(is_active=True).exclude(messages__isnull=False).distinct()
        by_type_token = {}
        for comm in affected_comms:
            for token in filter(None, (comm.type_tokens or "").split(",")):
                by_type_token.setdefault(token, 0)
                by_type_token[token] += 1
        self.stdout.write(
            f"Comunicacions sense missatge que es reassignaran: {affected_comms.count()} "
            f"(per type_tokens: {by_type_token})"
        )

        if not commit:
            self.stdout.write(self.style.WARNING(
                "DRY-RUN (no s'ha escrit res). Torna a executar amb --commit per aplicar-ho de veritat."
            ))
            return

        messages = [
            Message.objects.create(
                token=generate_token(Message),
                subject=message_type_template.subject,
                body=message_type_template.body,
                type=message_type_template.type,
            )
            for message_type_template in template_types
        ]
        process.messages.set(messages)
        self.stdout.write(self.style.SUCCESS(f"Creats {len(messages)} Message i associats al process."))

        updated = 0
        for comm in affected_comms:
            comm_type_tokens = [t for t in (comm.type_tokens or "").split(",") if t]
            if not comm_type_tokens:
                continue
            comm_types = MessageType.objects.filter(token__in=comm_type_tokens)
            comm.messages.set(process.messages.filter(type__in=comm_types))
            updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Fet. {updated} comunicacions reassignades amb el seu Message corresponent."
        ))
