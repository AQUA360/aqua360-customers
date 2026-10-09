import datetime
from typing import List, Dict, Any
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from billing.models import Invoice, Reading
from billing.tasks import generate_and_upload_xml
from claimrequest.tasks import generate_claim_document_pdf
from communication.utils.communication_service import create_email_template, get_communication_file
from contract.models import Contract
from coredata.models import ConfigProject, Person, PersonAddress
from communication.models import Communication, CommunicationFile, CommunicationStatus, CommunicationProcess, MessageType, MessageTypeTemplate, MessageTemplate
from coredata.serializers import PersonCommunicationSerializer
from coredata.utils.name_utils import generate_token
from documentmanager.models import Document
from logger.models import LogCommunicationStatusChange
from communication.tasks import generate_claim_document_pdf_task, generate_single_file_task
from documentmanager.utils.main_utils import upload_document
from django.core.files.base import ContentFile
from claimrequest.models import ClaimRequest
from billing.views.epayment_document_generate_view import generate_xml
from collections import defaultdict


def create_comm_from_persons(user, persons, process, company_config, msg_name, msg_token, fixed_data, attach_letter, progress_recorder=None, progress_start=10, progress_end=40, message_template_id=None, attach_invoices=False, company_config_email=None, attach_readings = False, attach_reading_invoices=False, attach_claim_documents=True):
    all_com_files_created = False
    created_files = []
    created_invoice_files = []
    try:
        invoice_type_invoice_token = ConfigProject.objects.get(token='invoice_type_invoice_token').value
        invoice_status_tokens = ConfigProject.objects.filter(
            token__in=[
                "invoice_status_pending_token",
                "invoice_status_cancelled_token",
                "invoice_status_payoff_token",
                "invoice_status_dropped_token"
            ]
        ).values_list('value', flat=True)
    except Exception as e:
        print(f"Error getting config data: {str(e)}")
        raise e
    
    def update_progress(current, total, description):
        if progress_recorder:
            percent = progress_start + int((current / total) * (progress_end - progress_start))
            progress_recorder.set_progress(percent, 100, description=description)
    try:
        with transaction.atomic():
            def _as_id_list(values):
                ids = []
                seen = set()
                for value in values or []:
                    value_id = value.get('id') if isinstance(value, dict) else value
                    if value_id is None or value_id in seen:
                        continue
                    seen.add(value_id)
                    ids.append(value_id)
                return ids

            def _append_unique(bucket, value):
                if value is not None and value not in bucket:
                    bucket.append(value)

            # Keep one group per payload row. Merging by person id collapsed
            # DIGITAL and PAPER contracts of the same titular into a single
            # communication (wrong channel + both invoices).
            person_groups = []
            for item in persons:
                person_groups.append({
                    'id': item['id'],
                    'contracts': _as_id_list(item.get('contracts')),
                    'invoices': _as_id_list(item.get('invoices')),
                    'readings': _as_id_list(item.get('readings')),
                })

            all_contract_ids = {cid for group in person_groups for cid in group['contracts']}
            all_invoice_ids = {iid for group in person_groups for iid in group['invoices']}
            all_reading_ids = {rid for group in person_groups for rid in group['readings']}

            invoice_contract_map = {}
            if all_invoice_ids:
                invoice_contract_map = dict(
                    Invoice.objects.filter(id__in=all_invoice_ids).values_list('id', 'contract_id')
                )
                all_contract_ids.update(cid for cid in invoice_contract_map.values() if cid)

            reading_contract_lookup = {}
            if all_reading_ids:
                reading_contract_lookup = dict(
                    Reading.objects.filter(id__in=all_reading_ids).values_list('id', 'contract_id')
                )
                all_contract_ids.update(cid for cid in reading_contract_lookup.values() if cid)

            contract_type_map = {}
            if all_contract_ids:
                contract_type_map = dict(
                    Contract.objects.filter(id__in=all_contract_ids).values_list('id', 'communication_type')
                )

            split_person_groups = []
            for group in person_groups:
                related_contract_ids = set(group['contracts'])
                for invoice_id in group['invoices']:
                    contract_id = invoice_contract_map.get(invoice_id)
                    if contract_id:
                        related_contract_ids.add(contract_id)
                for reading_id in group['readings']:
                    contract_id = reading_contract_lookup.get(reading_id)
                    if contract_id:
                        related_contract_ids.add(contract_id)

                communication_types = {
                    contract_type_map.get(contract_id)
                    for contract_id in related_contract_ids
                    if contract_type_map.get(contract_id) is not None
                }

                if len(communication_types) <= 1:
                    split_person_groups.append(group)
                    continue

                grouped_by_type = defaultdict(lambda: {'contracts': [], 'invoices': [], 'readings': []})
                for contract_id in group['contracts']:
                    comm_type = contract_type_map.get(contract_id)
                    _append_unique(grouped_by_type[comm_type]['contracts'], contract_id)
                for invoice_id in group['invoices']:
                    contract_id = invoice_contract_map.get(invoice_id)
                    comm_type = contract_type_map.get(contract_id) if contract_id else None
                    _append_unique(grouped_by_type[comm_type]['invoices'], invoice_id)
                    _append_unique(grouped_by_type[comm_type]['contracts'], contract_id)
                for reading_id in group['readings']:
                    contract_id = reading_contract_lookup.get(reading_id)
                    comm_type = contract_type_map.get(contract_id) if contract_id else None
                    _append_unique(grouped_by_type[comm_type]['readings'], reading_id)
                    _append_unique(grouped_by_type[comm_type]['contracts'], contract_id)

                for typed_group in grouped_by_type.values():
                    if typed_group['contracts'] or typed_group['invoices'] or typed_group['readings']:
                        split_person_groups.append({
                            'id': group['id'],
                            'contracts': typed_group['contracts'],
                            'invoices': typed_group['invoices'],
                            'readings': typed_group['readings'],
                        })

            person_ids = [group['id'] for group in split_person_groups]
            persons_map = {
                str(p.id): p for p in Person.objects.filter(id__in=person_ids)
            }
            print(f"persons_map: {persons_map}")
            print(f"split_person_groups: {split_person_groups}")

            serialized_persons = []
            for group in split_person_groups:
                person_in = persons_map.get(str(group['id']))
                if not person_in:
                    continue
                person_in.contract_ids = group['contracts']
                person_in.invoice_ids = group['invoices']
                person_in.reading_ids = group['readings']
                serialized_persons.append(PersonCommunicationSerializer(person_in).data)

            default_status = CommunicationStatus.objects.get(is_default=True)
            total_persons = len(serialized_persons)
            update_progress(0, max(total_persons, 1), f"Preparant creació de {total_persons} comunicacions")
            
            email_token = ConfigProject.objects.get(token='message_type_email_token').value
            letter_token = ConfigProject.objects.get(token='message_type_letter_token').value
            electronic_invoice_token = "electronic_inv"
            
            communications_to_create = []
            communication_payloads = []
            process_used_types = list(process.used_types.select_related('type', 'document').all())
            process_types_count = len(process_used_types)
            
            for idx, person in enumerate(serialized_persons):
                person_instance = persons_map.get(str(person['id']))
                print(f"person_instance: {person_instance}")
                if not person_instance:
                    continue
                
                invoices_to_attach = []
                if fixed_data:
                    if fixed_data == 'billing':
                        invoices_to_attach = Invoice.objects.filter(id__in=[item['id'] for item in person['invoices']])
                contract_com_type = person['com_type']
                if contract_com_type in ('PAPER', 'NONE'):
                    person['email'] = None
                final_tokens = []
                final_names = []
                
                for process_type in process_used_types:
                    if process_type.type.token == electronic_invoice_token and person.get('electronic_invoice'):
                        final_tokens.append(process_type.type.token)
                        final_names.append(process_type.type.name)
                    else:
                        if process_type.type.token == email_token and person.get('email'):
                            final_tokens.append(process_type.type.token)
                            final_names.append(process_type.type.name)
                        elif process_type.type.token == letter_token and person.get('address'):
                            final_tokens.append(process_type.type.token)
                            final_names.append(process_type.type.name)
                        
                type_tokens = ','.join(final_tokens)
                type_names = ','.join(final_names)
                electronic_invoice_data = person.get('electronic_invoice_data', None)
                reading_ids = [item['id'] for item in person.get('readings', [])]
                invoice_ids = [item['id'] for item in person.get('invoices', [])]
                contract_ids = person.get('contracts', [])
                communication_reading_groups = [[reading_id] for reading_id in reading_ids] if reading_ids else [[]]
                reading_contract_map = {}
                reading_invoice_map = defaultdict(list)
                if reading_ids:
                    reading_contract_map = dict(
                        Reading.objects.filter(id__in=reading_ids).values_list('id', 'contract_id')
                    )
                    if attach_reading_invoices:
                        reading_ids_set = set(reading_ids)
                        for reading_id, related_invoice_id in Invoice.objects.filter(
                            readings__id__in=reading_ids,
                            type_final=invoice_type_invoice_token
                        ).exclude(
                            status__token__in=invoice_status_tokens
                            ).distinct().values_list('readings__id', 'id'):
                            # the join can also return the other readings of the same invoice
                            if reading_id in reading_ids_set:
                                reading_invoice_map[reading_id].append(related_invoice_id)

                for communication_readings in communication_reading_groups:
                    communication_contract_ids = contract_ids
                    if communication_readings:
                        reading_contract_id = reading_contract_map.get(communication_readings[0])
                        if reading_contract_id:
                            communication_contract_ids = [reading_contract_id]
                    reading_invoice_ids = []
                    if attach_reading_invoices and communication_readings:
                        for communication_reading_id in communication_readings:
                            reading_invoice_ids.extend(reading_invoice_map.get(communication_reading_id, []))
                        reading_invoice_ids = list(dict.fromkeys(reading_invoice_ids))
                    comm = Communication(
                        token= generate_token(Communication, offset=len(communications_to_create)),
                        person=person_instance,
                        company_config=company_config,
                        company_config_email=company_config_email if company_config_email else company_config.company_config_emails.first(),
                        status=default_status,
                        process=process,
                        used_phones=person.get('sms_phone', None),
                        used_email=person.get('email', None),
                        used_address=person.get('address', None),
                        accounting_office=electronic_invoice_data.get('accounting_office', None) if electronic_invoice_data else None,
                        managing_body=electronic_invoice_data.get('managing_body', None) if electronic_invoice_data else None,
                        processing_unit=electronic_invoice_data.get('processing_unit', None) if electronic_invoice_data else None,
                        always_attach=attach_letter,
                        type_names=msg_name if process_types_count == 0 else type_names,
                        type_tokens=msg_token if process_types_count == 0 else type_tokens,
                        preferred_communication_type=contract_com_type,
                        user=user,
                    )
                    communications_to_create.append(comm)
                    communication_payloads.append({
                        'person_id': person['id'],
                        'contract_ids': communication_contract_ids,
                        'invoice_ids': invoice_ids,
                        'reading_ids': communication_readings,
                        'reading_invoice_ids': reading_invoice_ids,
                    })
                
                # Update progress for each person processed (first 60% of the range)
                update_progress(idx + 1, total_persons, f"Preparant comunicacions ({idx + 1}/{total_persons})")
            
            if communications_to_create:
                # Bulk create takes about 20% of the time
                update_progress(total_persons * 0.6, total_persons, "Creant comunicacions a la base de dades")
                created_communications = Communication.objects.bulk_create(communications_to_create)
                
                process_message_types = [msg_type.type for msg_type in process_used_types]
                for comm, types in zip(created_communications, [[] if process_types_count == 0 else process_message_types for _ in range(len(created_communications))]):
                    if types:
                        comm.types.set(types)
                
                for comm, payload in zip(created_communications, communication_payloads):
                    if payload.get('contract_ids'):
                        person_contracts = Contract.objects.filter(id__in=payload['contract_ids'])
                        comm.contracts.set(person_contracts)

                if process.type_tokens == 'default' or process.type_tokens == 'digital':
                    for comm in created_communications:
                        msg_type = None
                        if comm.preferred_communication_type == 'NONE':
                            # Contracte sense comunicació: no s'assigna cap canal (ni email, ni SMS, ni carta).
                            pass
                        elif comm.preferred_communication_type and process.type_tokens == 'default':
                            if comm.accounting_office and fixed_data and fixed_data == 'billing':
                                msg_type = MessageType.objects.get(token=electronic_invoice_token)
                                comm.messages.set(process.messages.filter(type=msg_type))
                            elif comm.preferred_communication_type == 'BOTH':
                                # Ambdues: correu i carta alhora; si falta un dels dos destins, només l'altre.
                                both_tokens = []
                                if comm.used_email:
                                    both_tokens.append(email_token)
                                if comm.used_address or not both_tokens:
                                    both_tokens.append(letter_token)
                                both_types = [MessageType.objects.get(token=token) for token in both_tokens]
                                comm.messages.set(process.messages.filter(type__in=both_types))
                                comm.types.set(both_types)
                                comm.type_tokens = ','.join(t.token for t in both_types)
                                comm.type_names = ','.join(t.name for t in both_types)
                                comm.save()
                                continue
                            else:
                                if comm.preferred_communication_type == 'DIGITAL' and comm.used_email is not None and comm.used_email != '':
                                    msg_type = MessageType.objects.get(token=email_token)
                                    comm.messages.set(process.messages.filter(type=msg_type))
                                else:
                                    msg_type = MessageType.objects.get(token=letter_token)
                                    comm.messages.set(process.messages.filter(type=msg_type))
                        elif process.type_tokens == 'digital':
                            msg_type = MessageType.objects.get(token=email_token)
                            comm.messages.set(process.messages.filter(type=msg_type))
                        else:
                            msg_type = MessageType.objects.get(token=letter_token)
                            comm.messages.set(process.messages.filter(type=msg_type))
                        if msg_type:
                            comm.types.set([msg_type])
                            comm.type_tokens = msg_type.token
                            comm.type_names = msg_type.name
                        else:
                            comm.messages.clear()
                            comm.types.clear()
                            comm.type_tokens = ''
                            comm.type_names = ''
                        comm.save()
                else:
                    for comm in created_communications:
                        process_messages = process.messages.all()
                        com_types = comm.types.all()
                        comm.messages.set(process_messages.filter(type__in=com_types))
                        comm.save()
                
                log_entries = [
                    LogCommunicationStatusChange(
                        object=comm,
                        previous_status=None,
                        current_status=default_status,
                        user=user,
                    ) for comm in created_communications
                ]
                LogCommunicationStatusChange.objects.bulk_create(log_entries)
                
                used_tokens = {
                    token.strip()
                    for comm in created_communications
                    for token in (comm.type_tokens or "").split(",")
                    if token and token.strip()
                }
                print(f"[comm-attach] process_id={process.id} used_tokens={sorted(list(used_tokens))}")

                template_rows = []
                if process_used_types:
                    template_rows = process_used_types
                    print(f"[comm-attach] template source=process.used_types count={len(template_rows)}")
                else:
                    template_instance = process.template
                    print(
                        f"[comm-attach] process.used_types empty; process.template_id={getattr(process, 'template_id', None)} "
                        f"message_template_id={message_template_id}"
                    )
                    if template_instance is None and message_template_id:
                        template_instance = MessageTemplate.objects.filter(id=message_template_id).first()
                        if template_instance is None:
                            template_instance = MessageTemplate.objects.filter(token=message_template_id).first()

                    if template_instance is not None:
                        print(
                            f"[comm-attach] template source=message_template id={template_instance.id} "
                            f"token={template_instance.token}"
                        )
                        through_model = MessageTemplate.templates.through
                        linked_template_type_ids = list(
                            through_model.objects.filter(
                                messagetemplate_id=template_instance.id
                            ).values_list("messagetypetemplate_id", flat=True)
                        )
                        print(
                            f"[comm-attach] through rows count={len(linked_template_type_ids)} "
                            f"messagetypetemplate_ids={linked_template_type_ids}"
                        )

                        if linked_template_type_ids:
                            template_rows = list(
                                MessageTypeTemplate.objects.select_related("type", "document")
                                .filter(id__in=linked_template_type_ids)
                                .order_by("-updated_at", "-id")
                            )
                        print(f"[comm-attach] template rows loaded by through ids={len(template_rows)}")
                    else:
                        print("[comm-attach] template resolution failed (no template instance)")

                template_documents_by_token = {}
                for template_row in template_rows:
                    if not template_row.type or not template_row.document:
                        print(
                            f"[comm-attach] skip template_row id={template_row.id} "
                            f"type={getattr(template_row.type, 'token', None)} document={getattr(template_row.document, 'id', None)}"
                        )
                        continue
                    token = template_row.type.token
                    if used_tokens and token not in used_tokens:
                        print(f"[comm-attach] skip token not used token={token}")
                        continue
                    if token not in template_documents_by_token:
                        template_documents_by_token[token] = template_row.document
                        print(
                            f"[comm-attach] mapped token={token} -> document_id={template_row.document.id}"
                        )

                print(
                    f"[comm-attach] final mapped tokens={sorted(list(template_documents_by_token.keys()))}"
                )

                com_files = []
                counter = 0
                for index, comm in enumerate(created_communications):
                    payload = communication_payloads[index] if index < len(communication_payloads) else {}
                    comm_tokens = set(filter(None, (comm.type_tokens or "").split(',')))
                    has_invoices = bool(payload.get('invoice_ids'))
                    print(
                        f"[comm-attach] communication_id={comm.id} type_tokens={sorted(list(comm_tokens))}"
                    )
                    print(f"letter token: {letter_token}")
                    # Cada destinatari postal necessita una carta, pero nomes una: cal mirar
                    # si el proces ja aporta un document que en fa de carta. A impagats el
                    # document del pas (avis d'impagats / carta de suspensio) ja n'es una de
                    # sencera; a facturacio (i amb `attach_invoices`) el document que s'envia
                    # es la factura. A devolucions SEPA nomes s'adjunten factures, i la
                    # notificacio no te cap altre lloc on anar en un enviament postal.
                    process_has_own_letter = (
                        attach_invoices
                        or fixed_data == 'billing'
                        or (fixed_data == 'claimrequest' and attach_claim_documents)
                    )
                    if attach_letter or (letter_token in comm_tokens and not process_has_own_letter):
                        print(f"[comm-attach] adding letter file for communication {comm.id}")
                        com_files.append(
                            CommunicationFile(
                                token=generate_token(CommunicationFile, offset=counter),
                                communication=comm,
                                file=None,
                                is_letter=True,
                            )
                        )
                        counter += 1

                    attached_document_ids = set()
                    for token in comm_tokens:
                        template_document = template_documents_by_token.get(token)
                        print(
                            f"[comm-attach] communication_id={comm.id} token={token} "
                            f"document_id={getattr(template_document, 'id', None)}"
                        )
                        if template_document and template_document.id not in attached_document_ids:
                            com_files.append(
                                CommunicationFile(
                                    token=generate_token(CommunicationFile, offset=counter),
                                    communication=comm,
                                    file=template_document,
                                    is_letter=False,
                                )
                            )
                            attached_document_ids.add(template_document.id)
                            counter += 1
                        
                        """ if token == letter_token:
                            com_files.append(
                                CommunicationFile(
                                    token=generate_token(CommunicationFile, offset=counter),
                                    communication=comm,
                                    file=None,
                                    is_letter=True,
                                )
                            )
                            counter += 1 """
                
                

                invoice_com_files = []
                electronic_invoice_com_files = []
                if (fixed_data and fixed_data == 'billing') or attach_invoices:
                    
                    for comm, payload in zip(created_communications, communication_payloads):
                        if payload.get('invoice_ids'):
                            person_invoices = Invoice.objects.filter(id__in=payload['invoice_ids'])
                            for invoice in person_invoices:
                                invoice_com_files.append(CommunicationFile(
                                    token=generate_token(CommunicationFile, offset=counter),
                                    communication=comm,
                                    file=invoice.invoice_file,
                                ))
                                counter += 1
                                # CREATE AND ADD ELECTRONIC INVOICE XML
                                if comm.accounting_office:
                                    try:
                                        xml_data = generate_xml(None, invoice)  
                                    except Exception as e:
                                        raise Exception(f"Error generating XML for invoice {invoice.serie_final}: {e}")
                                    xml_file_name = f"{invoice.serie_final.replace('/', '_')}_{invoice.id}.xml"
                                    
                                    try:
                                        existing_document = Document.objects.filter(
                                            entity='REBUTS',
                                            field='EFACTURA',
                                            entity_id=invoice.id,
                                            document_name=xml_file_name
                                        ).first()
                                    except Exception as e:
                                        print(f"Error getting existing document for invoice {invoice.serie_final}: {e}")
                                        existing_document = None
                                    if existing_document:
                                        document_file = existing_document
                                    else:
                                        xml_file = ContentFile(xml_data.encode("utf-8"), name=xml_file_name)
                                        document_file = upload_document(xml_file, 'REBUTS', 'EFACTURA', invoice.id, invoice.customer_token_final, '', settings.DOCUMENT_MANAGER_SERVICES.get("billing"), xml_file_name)
                                        invoice_com_files.append(CommunicationFile(
                                            token=generate_token(CommunicationFile, offset=counter),
                                            communication=comm,
                                            file=document_file,
                                        ))
                                        counter += 1
                                    
                        
                
                if attach_reading_invoices:
                    invoices_already_attached = bool((fixed_data and fixed_data == 'billing') or attach_invoices)
                    for comm, payload in zip(created_communications, communication_payloads):
                        if not payload.get('reading_invoice_ids'):
                            continue
                        reading_invoices = Invoice.objects.filter(id__in=payload['reading_invoice_ids'])
                        if invoices_already_attached and payload.get('invoice_ids'):
                            reading_invoices = reading_invoices.exclude(id__in=payload['invoice_ids'])
                        for invoice in reading_invoices:
                            if not invoice.invoice_file:
                                continue
                            invoice_com_files.append(CommunicationFile(
                                token=generate_token(CommunicationFile, offset=counter),
                                communication=comm,
                                file=invoice.invoice_file,
                            ))
                            counter += 1

                created_files = CommunicationFile.objects.bulk_create(com_files)
                # we create invoice files separately to avoid problems with later tasks
                created_invoice_files = CommunicationFile.objects.bulk_create(invoice_com_files)
                
                
                for comm, payload in zip(created_communications, communication_payloads):
                    if (fixed_data and fixed_data == 'billing') or attach_invoices:
                        if payload.get('invoice_ids'):
                            invoices_to_attach = Invoice.objects.filter(
                                id__in=payload['invoice_ids']
                            )
                            comm.invoices.set(invoices_to_attach)
                            if attach_readings:
                                readings_to_attach = Reading.objects.filter(invoices__in=invoices_to_attach)
                                comm.readings.set(readings_to_attach)
                    if payload.get('reading_ids'):
                        readings_to_attach = Reading.objects.filter(
                            id__in=payload['reading_ids']
                        )
                        comm.readings.set(readings_to_attach)
                    if attach_reading_invoices and payload.get('reading_invoice_ids'):
                        comm.invoices.add(*Invoice.objects.filter(id__in=payload['reading_invoice_ids']))
                
                # A impagats i devolucions SEPA les factures s'adjunten al pas seguent i el
                # cos de la carta les necessita per resoldre els `%invoice.*`: la carta es
                # deixa sense document i la renderitza `render_pending_letter_files()`.
                if fixed_data not in ('claimrequest', 'sepa_payments'):
                    for cr_comm_file in [cf for cf in created_files if getattr(cf, 'is_letter', False) and getattr(cf, 'file', None) is None]:
                        cr_comm_file.file = get_communication_file(cr_comm_file.id)
                        cr_comm_file.save()
                
                # Create email templates AFTER all communication data (including invoices) has been set
                email_comms = [comm for comm in created_communications if email_token in comm.type_tokens.split(',')]
                
                if email_comms:
                    update_progress(total_persons * 0.9, total_persons, "Generant plantilles d'email")
                    
                    for idx, comm in enumerate(email_comms):
                        if comm.messages.filter(type__token=email_token).exists():
                            create_email_template(comm)
                            if idx % 10 == 0 or idx == len(email_comms) - 1:  # Update every 10 emails and at the end
                                update_progress(
                                    total_persons * 0.9 + ((idx + 1) / len(email_comms)) * total_persons * 0.1,
                                    total_persons,
                                    f"Generant plantilles d'email ({idx + 1}/{len(email_comms)})"
                                )
                
                update_progress(total_persons, total_persons, f"Comunicacions creades correctament ({len(created_communications)})")
                all_com_files_created = True

        """ if all_com_files_created:
            try:
                for comm_file in created_files:
                    comm_file.refresh_from_db()
                    generate_single_file_task.delay(comm_file.id)
                if fixed_data and fixed_data == 'claimrequest':
                    created_communications_ids = [comm.id for comm in created_communications]
                    generate_claim_document_pdf_task(created_communications_ids, process.id)
            except Exception as e:
                all_com_files_created = False
                print(f"Error scheduling communication file tasks: {str(e)}") """
                
        return all_com_files_created
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error creating communications: {str(e)}")
        raise
    