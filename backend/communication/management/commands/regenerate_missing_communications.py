"""
Regenera les comunicacions que falten per a una facturació concreta (billing_id),
processant els titulars en lots petits perquè, si algun registre concret peta
(p.ex. un error generant l'XML de factura electrònica d'un client), només es
perdi aquest lot petit i no tota la tanda -- que és el que va passar amb els
"Lot 1/3" de billing_id 84 i 85 (transaction.atomic() al voltant de tot el lot
feia rollback complet davant de qualsevol excepció).

No envia res als clients: crea les Communication/CommunicationFile en estat
"Pendent" (igual que fa la resta del procés normal). L'enviament és una acció
posterior i separada.

Ús:
  # 1) Comprovar què es generaria, sense escriure res:
  python manage.py regenerate_missing_communications 84 --dry-run

  # 2) Executar de veritat, en lots de 20 titulars:
  python manage.py regenerate_missing_communications 84 --commit --chunk-size 20

  # Repetir per l'altra facturació:
  python manage.py regenerate_missing_communications 85 --commit --chunk-size 20
"""
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from billing.models import Invoice
from communication.models import CommunicationProcess, CommunicationProcessStatus, Message, MessageTemplate
from communication.utils.message_service import create_comm_from_persons
from coredata.models import ConfigProject, Person
from coredata.utils.name_utils import generate_token
from logger.models import LogCommunicationProcessStatusChange
from service.models import CompanyConfig, CompanyConfigEmail


class Command(BaseCommand):
    help = (
        "Regenera, en lots petits, les comunicacions que falten per a un billing_id "
        "concret (factures sense cap Communication associada)."
    )

    def add_arguments(self, parser):
        parser.add_argument("billing_id", type=int)
        parser.add_argument("--chunk-size", type=int, default=20,
                             help="Titulars per lot (per aïllar registres problemàtics). Default 20.")
        parser.add_argument("--commit", action="store_true",
                             help="Sense aquest flag NOMÉS es mostra el que es faria (dry-run per defecte).")
        parser.add_argument("--user-id", type=int, default=7,
                             help="Usuari que apareix com a autor del procés/comunicacions.")
        parser.add_argument("--template-id", type=int, default=3)
        parser.add_argument("--use-type-id", type=int, default=3)
        parser.add_argument("--company-config-id", type=int, default=1)
        parser.add_argument("--company-config-email-id", type=int, default=1)
        parser.add_argument("--msg-token", type=str, default="default")
        parser.add_argument(
            "--msg-name", type=str,
            default="Predefinit al contracte (Segons prioritat al contracte: Postal o Digital)",
        )
        parser.add_argument("--attach-letter", action="store_true", default=True)
        parser.add_argument("--no-attach-letter", dest="attach_letter", action="store_false")

    def handle(self, *args, **options):
        billing_id = options["billing_id"]
        chunk_size = options["chunk_size"]
        commit = options["commit"]

        invoices = (
            Invoice.objects.filter(billing_id=billing_id, communications__isnull=True)
            .select_related("contract", "contract__holder")
            .order_by("id")
        )
        total_invoices = invoices.count()
        if total_invoices == 0:
            self.stdout.write(self.style.SUCCESS(
                f"No hi ha cap factura sense comunicació per billing_id={billing_id}."
            ))
            return

        by_person = defaultdict(lambda: {"invoices": set(), "contracts": set()})
        skipped_no_holder = []
        for inv in invoices:
            contract = inv.contract
            holder = contract.holder if contract else None
            if not holder:
                skipped_no_holder.append(inv.id)
                continue
            by_person[holder.id]["invoices"].add(inv.id)
            by_person[holder.id]["contracts"].add(contract.id)

        person_ids = list(by_person.keys())
        self.stdout.write(
            f"billing_id={billing_id}: {total_invoices} factures sense comunicació, "
            f"agrupades en {len(person_ids)} titulars."
        )
        if skipped_no_holder:
            self.stdout.write(self.style.WARNING(
                f"  {len(skipped_no_holder)} factures sense titular (contract.holder buit), "
                f"es descarten: {skipped_no_holder}"
            ))

        chunks = [person_ids[i:i + chunk_size] for i in range(0, len(person_ids), chunk_size)]
        self.stdout.write(f"Es processaran en {len(chunks)} lots de fins a {chunk_size} titulars.")

        if not commit:
            self.stdout.write(self.style.WARNING(
                "DRY-RUN (no s'ha escrit res). Torna a executar amb --commit per aplicar-ho de veritat."
            ))
            return

        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.filter(id=options["user_id"]).first()

        company_config = CompanyConfig.objects.filter(id=options["company_config_id"]).first()
        company_config_email = CompanyConfigEmail.objects.filter(id=options["company_config_email_id"]).first()

        status_processing = CommunicationProcessStatus.objects.get(
            token=ConfigProject.objects.get(token="communication_process_status_processing_token").value
        )
        status_files_created = CommunicationProcessStatus.objects.get(
            token=ConfigProject.objects.get(token="communication_process_status_files_created_token").value
        )
        status_default = CommunicationProcessStatus.objects.get(is_default=True)

        process = CommunicationProcess.objects.create(
            token=generate_token(CommunicationProcess),
            description=f"Regeneració comunicacions pendents - billing_id {billing_id}",
            type_tokens=options["msg_token"],
            type_names=options["msg_name"],
            separate_communications=False,
            status=status_processing,
            template_id=options["template_id"],
            use_type_id=options["use_type_id"],
            user=user,
        )
        LogCommunicationProcessStatusChange.objects.create(
            object=process, previous_status=None, current_status=status_processing, user=user,
        )
        self.stdout.write(self.style.SUCCESS(f"Creat CommunicationProcess id={process.id} token={process.token}"))

        # Cal generar els Message (subjecte/cos) a partir del MessageTemplate i penjar-los
        # al procés -- igual que fa ManageCommunicationProcessViewSet.create() amb
        # `messages_data` -- perquè send_electronic_mail() en depèn (comm.messages, i com a
        # fallback comm.process.messages) per obtenir el subjecte/cos del correu. Sense això
        # el DoesNotExist queda sense capturar i la comunicació es queda "Pendent" per sempre
        # (l'excepció es perd silenciosament al bucle de send_communications_task).
        template_instance = MessageTemplate.objects.filter(id=options["template_id"]).first()
        if template_instance:
            messages = [
                Message.objects.create(
                    token=generate_token(Message),
                    subject=message_type_template.subject,
                    body=message_type_template.body,
                    type=message_type_template.type,
                )
                for message_type_template in template_instance.templates.select_related("type").all()
            ]
            process.messages.set(messages)
            self.stdout.write(self.style.SUCCESS(
                f"  Missatges generats des del template id={template_instance.id}: "
                f"{[m.type.token for m in messages]}"
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"  No s'ha trobat cap MessageTemplate amb id={options['template_id']}; "
                f"les comunicacions per email es quedaran sense enviar."
            ))

        ok_persons = 0
        failed_chunks = []
        for idx, chunk_person_ids in enumerate(chunks, start=1):
            persons_payload = [
                {
                    "id": pid,
                    "contracts": list(by_person[pid]["contracts"]),
                    "invoices": list(by_person[pid]["invoices"]),
                    "readings": [],
                }
                for pid in chunk_person_ids
            ]
            try:
                with transaction.atomic():
                    create_comm_from_persons(
                        user,
                        persons_payload,
                        process,
                        company_config,
                        options["msg_name"],
                        options["msg_token"],
                        "billing",
                        options["attach_letter"],
                        message_template_id=options["template_id"],
                        attach_invoices=True,
                        company_config_email=company_config_email,
                        attach_readings=False,
                        attach_reading_invoices=False,
                    )
                ok_persons += len(chunk_person_ids)
                self.stdout.write(f"  Lot {idx}/{len(chunks)}: OK ({len(chunk_person_ids)} titulars)")
            except Exception as e:
                failed_chunks.append((chunk_person_ids, str(e)))
                self.stdout.write(self.style.ERROR(
                    f"  Lot {idx}/{len(chunks)}: ERROR ({len(chunk_person_ids)} titulars) -> {e}"
                ))

        process.refresh_from_db()
        final_status = status_files_created if not failed_chunks else status_default
        LogCommunicationProcessStatusChange.objects.create(
            object=process, previous_status=process.status, current_status=final_status, user=user,
        )
        process.status = final_status
        process.save(update_fields=["status"])

        self.stdout.write(self.style.SUCCESS(
            f"Fet. Titulars processats correctament: {ok_persons}/{len(person_ids)}."
        ))

        if failed_chunks:
            self.stdout.write(self.style.ERROR(
                f"\n{len(failed_chunks)} lot(s) han fallat. Torna a executar aquest mateix "
                f"command només per aquests titulars (reduint --chunk-size, p.ex. 1) per "
                f"aïllar exactament quin contracte/factura provoca l'error:"
            ))
            for person_ids_failed, err in failed_chunks:
                self.stdout.write(f"  persons={person_ids_failed} -> {err}")
