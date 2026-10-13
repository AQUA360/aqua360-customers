import uuid
from celery import shared_task, group, current_task
from celery_progress.backend import ProgressRecorder
from datetime import timedelta
from django.conf import settings
from django.utils import timezone, translation
from django.utils.translation import gettext as _, gettext_lazy
from celery import states
from billing.models import Invoice, PaymentRemittance
from billing.utils.payment_pdf_service import generate_report_payment_pdf
from claimrequest.models import ClaimRequest
from communication.models import Communication, CommunicationProcessStatus, CommunicationProcess, CommunicationFile, CommunicationStatus, Message, MessageType
from communication.utils.communication_service import create_email_template, handle_communication, get_communication_file
from coredata.models import ConfigProject
from coredata.utils.name_utils import generate_token
from claimrequest.tasks import generate_claim_document_pdf
from documentmanager.utils.main_utils import upload_document
from notification.models import Notification
from django.core.files.base import ContentFile

from service.models import CompanyConfigEmail

@shared_task
def send_communications_task(process_id=None, communication_ids=None, batch_size=5, only_returned=False):
    try:
        try:
            pending_status = CommunicationStatus.objects.get(is_default=True)
        except CommunicationStatus.DoesNotExist:
            print("Error: No default CommunicationStatus found. Cannot process communications.")
            return {"status": "error", "message": "No default CommunicationStatus found"}
        
        try:
            rejected_token = ConfigProject.objects.get(token='communication_status_rejected_token').value
        except Exception as e:
            rejected_token = '-2'
        
        try:
            comm_sent_token = ConfigProject.objects.get(token='communication_status_sent_token').value
        except Exception as e:
            comm_sent_token = '2'
        status_rejected = CommunicationStatus.objects.get(token=rejected_token)
        
        if process_id:
            try:
                process = CommunicationProcess.objects.get(id=process_id)
            except CommunicationProcess.DoesNotExist:
                print(f"Error: Process with id {process_id} not found.")
                return {"status": "error", "message": f"Process with id {process_id} not found"}
            communications = process.communications.all().exclude(type_tokens="letter")
            # If we received a restricted list of IDs, only work on that subset
            if communication_ids is not None:
                communications = communications.filter(id__in=communication_ids)
            if only_returned:
                communications = communications.filter(status=status_rejected).distinct()
            else:
                communications = communications.filter(status=pending_status).distinct()
        else:
            if communication_ids is None:
                communications = Communication.objects.none()
            else:
                communications = Communication.objects.filter(id__in=communication_ids).exclude(type_tokens="letter")
                if only_returned:
                    communications = communications.filter(status=status_rejected).distinct()
                else:
                    communications = communications.filter(status=pending_status).distinct()

        if (not communications.exists() or len(communications) == 0) and communication_ids is not None:
            communications = Communication.objects.filter(id__in=communication_ids).exclude(type_tokens="letter").exclude(status__token=comm_sent_token).distinct()
            if only_returned:
                communications = communications.filter(rejection_reason__isnull=False)

        # Get a batch of communications
        batch = communications[:batch_size]

        # Process each communication in the batch
        for comm in batch:
            try:
                comm_types = comm.type_tokens.split(',') if comm.type_tokens else []
                if comm_types:
                    handle_communication(comm, comm_types)
            except Exception as e:
                print(f"Error sending communication: {str(e)}")
                continue

        # Determine remaining communications:
        # - If we were given an explicit list of IDs, walk that list.
        # - Otherwise (first process-based run), derive IDs from the current queryset.
        # if communication_ids is not None:
        #     ids_list = list(communication_ids)
        # else:
        ids_list = list(communications.values_list("id", flat=True))

        processed_ids = [comm.id for comm in batch]
        remaining_ids = [cid for cid in ids_list if cid not in processed_ids]
        remaining_count = len(remaining_ids)

        # Schedule next batch if there are more communications
        if remaining_count > 0:
            try:
                if process_id:
                    # Pass the remaining IDs so subsequent runs only see not-yet-processed communications
                    send_communications_task.apply_async(
                        args=[process_id, remaining_ids, batch_size],
                        kwargs={"only_returned": only_returned},
                        countdown=90,  # 1.5 minute delay
                    )
                else:
                    send_communications_task.apply_async(
                        args=[None, remaining_ids, batch_size],
                        kwargs={"only_returned": only_returned},
                        countdown=90,  # 1.5 minute delay
                    )
            except Exception as e:
                print(f"Error scheduling next batch: {str(e)}")
        else:
            if process_id:
                try:
                    notification_save = {
                        "token": uuid.uuid4(),
                        "name": "Comunicacions enviades",
                        "description": "Totes les comunicacions s'han enviat correctament",
                        "module": "communication",
                        "entity": "process-communications",
                        "object_id": process_id,
                        "is_active": True,
                    }
                    Notification.objects.create(**notification_save)
                    try:
                        if all(communication.status.token == comm_sent_token for communication in process.communications.all()):
                            status_finalized_token = ConfigProject.objects.get(token='communication_process_status_finalized_token').value
                            status_current = CommunicationProcessStatus.objects.get(token=status_finalized_token)
                        else:
                            status_current_token = ConfigProject.objects.get(
                                token="communication_process_status_current_token"
                            ).value
                            status_current = CommunicationProcessStatus.objects.get(token=status_current_token)
                        process.status = status_current
                        process.save()
                    except (ConfigProject.DoesNotExist, CommunicationProcessStatus.DoesNotExist) as e:
                        print(f"Error updating process status: {str(e)}")
                except Exception as e:
                    print(f"Error creating notification or updating process: {str(e)}")

        return {
            "status": "success",
            "processed": len(batch),
            "total": len(communications),
            "remaining": remaining_count,
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)} 

@shared_task
def generate_single_file_task(comm_file_id, parent_task_id=None):
    try:
        comm_file = CommunicationFile.objects.get(id=comm_file_id)
        n_file = get_communication_file(comm_file_id)
        if n_file:
            comm_file.file = n_file
            comm_file.save()
            
            if parent_task_id:
                parent_result = generate_files_task.AsyncResult(parent_task_id)
                if parent_result.ready():
                    all_subtasks = [generate_single_file_task.AsyncResult(task_id) for task_id in parent_result.children]
                    if all(task.state == states.SUCCESS for task in all_subtasks):
                        # Create notification when all files are generated
                        notification_save = {
                            'token': uuid.uuid4(),
                            'name': "Documents generats",
                            'description': f"Tots els documents ({len(all_subtasks)}) s'han generat correctament",
                            'module': 'communication',
                            'entity': 'communications',
                            'object_id': comm_file.communication.id,
                            'is_active': True
                        }
                        Notification.objects.create(**notification_save)
            
            return {
                "status": "success",
                "communication_file_id": comm_file_id,
                "communication_id": comm_file.communication.id,
            }
        else:
            return {
                "status": "error",
                "communication_file_id": comm_file_id,
                "message": "Communication file not found"
            }
    except Exception as e:
        return {
            "status": "error",
            "communication_file_id": comm_file_id,
            "message": str(e)
        }

@shared_task
def generate_files_task(communication_ids):
    print(f"[generate_files_task] Generating files for communications {communication_ids}")
    try:
        communications = Communication.objects.filter(id__in=communication_ids)
        print(f"[generate_files_task] Communications found: {communications.count()}")
        
        # CHECK IF COMMS ALREADY HAD LETTER FILES
        # Nomes les cartes de les comunicacions que s'estan regenerant: sense el filtre
        # per comunicacio es desactivaven totes les cartes de la base de dades.
        existing_comm_files = CommunicationFile.objects.filter(
            is_letter=True, communication__in=communications
        )
        existing_comm_files.update(is_active=False)
        
        com_files = [
            CommunicationFile(
                token=generate_token(CommunicationFile, offset=counter),
                communication=comm,
                file=None,
                is_letter=True,
            ) for counter, comm in enumerate(communications)
        ]
        print(f"[generate_files_task] Communication files created: {com_files}")
        created_files = CommunicationFile.objects.bulk_create(com_files)
        
        task_id = current_task.request.id if current_task else None
        print(f"[generate_files_task] Task id: {task_id}")
        
        file_tasks = []
        print(f"[generate_files_task] File tasks created: {file_tasks}")

        for comm_file in created_files:
            print(f"Generating file for communication {comm_file.communication.id}")
            subtask = generate_single_file_task.s(comm_file.id, task_id)
            file_tasks.append(subtask)
        if len(created_files) == len(communications):
            status_default = CommunicationStatus.objects.get(is_default=True)
            status_files_created = CommunicationStatus.objects.get(token=ConfigProject.objects.get(token='communication_process_status_files_created_token').value)
            communication_processes = CommunicationProcess.objects.filter(communications__in=communications)
            communication_processes.update(status=status_files_created)
            
        # Execute tasks as a group
        group(file_tasks).apply_async()
        
        return {
            "status": "success",
            "total_files": len(created_files),
            "message": "File generation tasks started"
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)} 

@shared_task
def check_send_date():
    try:
        pending_status = CommunicationStatus.objects.get(is_default=True)
        communications = Communication.objects.filter(due_date__lte=timezone.now(), is_active=True, status=pending_status)
        #send communications task
        communication_ids = list(communications.values_list('id', flat=True))
        send_communications_task.delay(None, communication_ids)
        
        notification_save = {
        'token': uuid.uuid4(),
        'name': f"Comunicacions enviades",
        'description': f"{len(communications)} comunicacions enviades al {timezone.now().strftime('%d/%m/%Y')}",
        'module': 'communication',
        'entity': 'communication',
        'object_id': None,
        'is_active': True
        }
        notification = Notification.objects.create(**notification_save)
        
        return {
            "status": "success",
            "total_communications": len(communications)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)} 

def _create_claim_step_communication_file(
    claim_request,
    contract,
    comm,
    service,
    counter,
    attach_claim_documents,
    joined_payment_id=None,
):
    """Generate the claim-step PDF, archive it on the communication, and
    optionally send it with the communication, by email or by letter. The unpaid
    invoice and payment slip (created separately) are unaffected by
    `attach_claim_documents`.
    """
    pdf_args = [claim_request.id, contract.id, claim_request.current_step.id]
    if joined_payment_id is not None:
        pdf_args.append(joined_payment_id)
    result = generate_claim_document_pdf(*pdf_args)
    token = generate_token(CommunicationFile, offset=counter)
    document = upload_document(
        ContentFile(result["pdf_content"]),
        'COMUNICACIO',
        'COMUNICACIO',
        comm.id,
        comm.token,
        '',
        service,
        f"{token}.pdf",
    )
    return CommunicationFile(
        token=token,
        communication=comm,
        file=document,
        attach_to_email=attach_claim_documents,
        attach_to_letter=attach_claim_documents,
    )

def render_pending_letter_files(communication_ids):
    """Renderitza les cartes creades sense document.

    A impagats i devolucions SEPA la carta no es pot renderitzar a
    `create_comm_from_persons`: el cos resol `%invoice.*` i les factures no s'adjunten
    fins al pas seguent.
    """
    pending = CommunicationFile.objects.filter(
        communication_id__in=communication_ids, is_letter=True, file__isnull=True, is_active=True
    )
    for comm_file in pending:
        try:
            comm_file.file = get_communication_file(comm_file.id)
            comm_file.save()
        except Exception as e:
            print(f"Error rendering letter for communication file {comm_file.id}: {str(e)}")

@shared_task
def generate_claim_document_pdf_task(communication_ids, process_id, progress_recorder=None, progress_start=70, progress_end=90, claim_id = None, attach_claim_documents=True):
    try:
        service = settings.DOCUMENT_MANAGER_SERVICES.get("communication")
        claim_com_files = []
        counter = 0
        communications = Communication.objects.filter(id__in=communication_ids)
        process = CommunicationProcess.objects.get(id=process_id)
        
        claim_request = ClaimRequest.objects.get(id=claim_id) if claim_id else ClaimRequest.objects.get(current_step__communication_process=process, current_step__is_completed=False)
        
        # Count total contracts to process
        total_contracts = sum(comm.contracts.count() for comm in communications)
        processed_contracts = 0
        print(f"Total contracts: {total_contracts}")
        # make limit here 2 months forward from today
        limit_date = timezone.now() + timedelta(days=60)
        email_token = ConfigProject.objects.get(token='message_type_email_token').value
        for comm in communications:
            print(f"Communication: {comm.id}")
            invoice_attached_to_comm = False
            for contract in comm.contracts.all():
                # Collect all invoices for this claim_request/contract pair
                claim_payments = claim_request.payments.filter(contract=contract).select_related("payment__invoice")
                joined_payments = claim_request.joined_payments.filter(contract=contract).values_list('id', flat=True)
                add_joined_payments = bool(
                    joined_payments.exists()
                    and claim_request.current_step.step_template.group_payments
                )

                if not claim_payments.exists() or add_joined_payments:
                    print(f"No ClaimRequestPayment found for contract {contract.id}")
                else:
                    for cr_payment in claim_payments:
                        invoice = getattr(getattr(cr_payment, "payment", None), "invoice", None)
                        if invoice and getattr(invoice, "invoice_file", None):
                            comm.invoices.add(invoice)
                            invoice_attached_to_comm = True
                            claim_com_files.append(
                                CommunicationFile(
                                    token=generate_token(CommunicationFile, offset=counter),
                                    communication=comm,
                                    file=invoice.invoice_file,
                                )
                            )
                            counter += 1
                            if not cr_payment.claim_step and not add_joined_payments:
                                try:
                                    payment_file, _ = generate_report_payment_pdf(cr_payment.payment, None, limit_date = limit_date)
                                    claim_com_files.append(
                                        CommunicationFile(
                                            token=generate_token(CommunicationFile, offset=counter),
                                            communication=comm,
                                            file=payment_file,
                                        )
                                    )
                                    counter += 1
                                except Exception as e:
                                    print(f"Error generating payment PDF: {str(e)}")
                        else:
                            print(f"NO INVOICE FILE FOUND for ClaimRequestPayment {cr_payment.id}")

                joined_payment_ids = joined_payments if add_joined_payments else [None]
                for joined_payment_id in joined_payment_ids:
                    claim_com_files.append(
                        _create_claim_step_communication_file(
                            claim_request,
                            contract,
                            comm,
                            service,
                            counter,
                            attach_claim_documents,
                            joined_payment_id,
                        )
                    )
                    counter += 1
                processed_contracts += 1
                
                # Update progress
                if progress_recorder and total_contracts > 0:
                    percent = progress_start + int((processed_contracts / total_contracts) * (progress_end - progress_start))
                    progress_recorder.set_progress(
                        percent, 
                        100, 
                        description=f"Generant documents de reclamació ({processed_contracts}/{total_contracts})"
                    )

            if invoice_attached_to_comm and email_token in comm.type_tokens.split(',') and comm.messages.filter(type__token=email_token).exists():
                create_email_template(comm)

        print(f"Claim com files: {claim_com_files}")
        created_claim_files = CommunicationFile.objects.bulk_create(claim_com_files)
        print(f"Created claim files: {created_claim_files}")
        return {
            "status": "success",
            "total_files": len(created_claim_files),
            "message": "Claim document PDF generation tasks started"
        }
    except Exception as e:
        print(f"Error generating claim document PDF: {str(e)}")
        return {"status": "error", "message": str(e)} 

@shared_task
def generate_sepa_payments_document_pdf_task(communication_ids, process_id, progress_recorder=None, progress_start=70, progress_end=90, sepa_remittance_id = None):
    try:
        service = settings.DOCUMENT_MANAGER_SERVICES.get("communication")
        sepa_com_files = []
        counter = 0
        
        communications = Communication.objects.filter(id__in=communication_ids)
        sepa_remittance = PaymentRemittance.objects.get(id=sepa_remittance_id) if sepa_remittance_id else None
        
        # Count total contracts to process
        total_contracts = sum(comm.contracts.count() for comm in communications)
        processed_contracts = 0
        print(f"Total contracts: {total_contracts}")
        for comm in communications:
            print(f"Communication: {comm.id}")
            for contract in comm.contracts.all():
                # Collect all invoices for this claim_request/contract pair
                contract_payments = sepa_remittance.payments.filter(contract=contract).select_related("payment__invoice")

                if not contract_payments.exists():
                    print(f"No ClaimRequestPayment found for contract {contract.id}")
                else:
                    for c_payment in contract_payments:
                        invoice = getattr(getattr(c_payment, "payment", None), "invoice", None)
                        if invoice and getattr(invoice, "invoice_file", None):
                            print(f"Invoice found: {invoice.id} for contract {contract.id}")
                            comm.invoices.add(invoice)
                            sepa_com_files.append(
                                CommunicationFile(
                                    token=generate_token(CommunicationFile, offset=counter),
                                    communication=comm,
                                    file=invoice.invoice_file,
                                )
                            )
                            counter += 1
                        else:
                            print(f"NO INVOICE FILE FOUND for ContractPayment {c_payment.id}")
                processed_contracts += 1
                
                # Update progress
                if progress_recorder and total_contracts > 0:
                    percent = progress_start + int((processed_contracts / total_contracts) * (progress_end - progress_start))
                    progress_recorder.set_progress(
                        percent, 
                        100, 
                        description=f"Generant documents de reclamació ({processed_contracts}/{total_contracts})"
                    )
        print(f"Sepa com files: {sepa_com_files}")
        created_sepa_files = CommunicationFile.objects.bulk_create(sepa_com_files)
        print(f"Created sepa files: {created_sepa_files}")
        return {
            "status": "success",
            "total_files": len(created_sepa_files),
            "message": "Sepa document PDF generation tasks started"
        }
    except Exception as e:
        print(f"Error generating sepa document PDF: {str(e)}")
        return {"status": "error", "message": str(e)} 

@shared_task
def generate_communication_invoice_documents_task(communication_ids):
    try:
        communications = Communication.objects.filter(id__in=communication_ids)
        counter = 0
        files_to_create = []
        for comm in communications:
            has_electronic_inv = True if 'electronic_inv' in comm.type_tokens.split(',') else False
            for invoice in comm.invoices.all():
                if not invoice.invoice_file:
                    from billing.views.invoice_pdf_view import generate_report_invoice_pdf
                    generate_report_invoice_pdf(invoice)
                    
                files_to_create.append(CommunicationFile(
                    token=generate_token(CommunicationFile, offset=counter),
                    communication=comm,
                    file=invoice.invoice_file,
                ))
                counter += 1
                if has_electronic_inv:
                    xml_file_name = f"{invoice.serie_final.replace('/', '_')}_{invoice.id}.xml"
                    try:
                        from documentmanager.models import Document
                        document_file = Document.objects.filter(
                            entity='REBUTS',
                            field='EFACTURA',
                            entity_id=invoice.id,
                            document_name=xml_file_name
                        ).first()
                    except Exception as e:
                        print(f"Error getting existing document for invoice {invoice.serie_final}: {e}")
                        document_file = None
                    if not document_file:
                        from billing.views.epayment_document_generate_view import generate_xml
                        try:
                            xml_data = generate_xml(None, invoice)  
                        except Exception as e:
                            raise Exception(f"Error generating XML for invoice {invoice.serie_final}: {e}")
                        xml_file = ContentFile(xml_data.encode("utf-8"), name=xml_file_name)
                        document_file = upload_document(xml_file, 'REBUTS', 'EFACTURA', invoice.id, invoice.customer_token_final, '', settings.DOCUMENT_MANAGER_SERVICES.get("billing"), xml_file_name)
                    files_to_create.append(CommunicationFile(
                        token=generate_token(CommunicationFile, offset=counter),
                        communication=comm,
                        file=document_file,
                    ))
                    counter += 1
                    
        created_files = CommunicationFile.objects.bulk_create(files_to_create)
        return {
            "status": "success",
            "total_files": len(created_files),
            "message": "Communication invoice documents generation tasks started"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)} 

@shared_task
def generate_communication_files(communication_ids):
    try:
        communications = Communication.objects.filter(id__in=communication_ids)
        com_files = [
            CommunicationFile(
                token=generate_token(CommunicationFile, offset=counter),
                communication=comm,
                file=None,
            ) for counter, comm in enumerate(communications)
        ]
        created_files = CommunicationFile.objects.bulk_create(com_files)
        for comm_file in created_files:
            generate_single_file_task.delay(comm_file.id)
        return {
            "status": "success",
            "total_files": len(created_files),
            "message": "Communication files generation tasks started"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@shared_task(bind=True)
def process_communication_creation_task(self, process_id, user_id, persons, company_config_id, single_name, msg_tokens, fixed_data, attach_letter, fixed_data_id, message_template_id, attach_invoices, company_config_email_id, attach_claim_documents=True, attach_readings=False, attach_reading_invoices=False):
    """
    Task to handle the full communication creation process with granular progress tracking:
    1. Change status to processing (0-10%)
    2. Create communications from persons (10-40%)
    3. Get communication IDs (40-50%)
    4. Generate communication files and claim documents (50-90%)
    5. Update final status (90-100%)
    """
    progress_recorder = ProgressRecorder(self)
    
    try:
        from communication.models import CommunicationProcessStatus
        from communication.utils.message_service import create_comm_from_persons
        from logger.models import LogCommunicationProcessStatusChange
        from service.models import CompanyConfig
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        # Get instances
        instance = CommunicationProcess.objects.get(id=process_id)
        user = User.objects.get(id=user_id) if user_id else None
        company_config = CompanyConfig.objects.get(id=company_config_id) if company_config_id else None
        company_config_email = CompanyConfigEmail.objects.get(id=company_config_email_id) if company_config_email_id else None
        
        # Save task_id to process
        instance.task_id = self.request.id
        instance.save(update_fields=['task_id'])
        
        # Step 1: Change status to processing (0-10%)
        progress_recorder.set_progress(0, 100, description="Canviant estat a processant")
        
        status_processing = CommunicationProcessStatus.objects.get(
            token=ConfigProject.objects.get(token="communication_process_status_processing_token").value
        )
        LogCommunicationProcessStatusChange.objects.create(
            object=instance,
            previous_status=instance.status,
            current_status=status_processing,
            user=user,
        )
        instance.status = status_processing
        instance.save()
        
        progress_recorder.set_progress(10, 100, description="Estat canviat a processant")
        
        # Step 2: Create communications from persons (10-40%)
        # Pass progress recorder to track each person being processed
        all_com_files_created = create_comm_from_persons(
            user, persons, instance, company_config, single_name, msg_tokens, fixed_data, attach_letter,
            progress_recorder=progress_recorder, progress_start=10, progress_end=40, 
            message_template_id=message_template_id, attach_invoices=attach_invoices,
            company_config_email=company_config_email, attach_readings=attach_readings,
            attach_reading_invoices=attach_reading_invoices,
            attach_claim_documents=attach_claim_documents
        )
        
        # Step 3: Get communication IDs (40-50%)
        progress_recorder.set_progress(40, 100, description="Obtenint IDs de comunicació")
        
        communications = instance.communications.all()
        communication_ids = [comm.id for comm in communications]
        total_communications = len(communication_ids)
        
        progress_recorder.set_progress(50, 100, description=f"IDs obtinguts ({total_communications} comunicacions)")
        
        print(f"Communication IDs: {communication_ids}")
        # Step 4: Generate files and claim documents (50-90%)
        if communication_ids:
            try:
                # Generate communication files inline with progress tracking
                progress_recorder.set_progress(50, 100, description="Generant fitxers de comunicació")
                
                service = settings.DOCUMENT_MANAGER_SERVICES.get("communication")
                com_files = []
                print(f"Fixed data: {fixed_data}")
                """ for counter, comm_id in enumerate(communication_ids):
                    comm = Communication.objects.get(id=comm_id)
                    comm_file = CommunicationFile(
                        token=generate_token(CommunicationFile, offset=counter),
                        communication=comm,
                        file=None,
                        is_letter=True,
                    )
                    com_files.append(comm_file)
                
                created_files = CommunicationFile.objects.bulk_create(com_files) """
                
                # Generate each file with progress tracking (50-70%)
                files_progress_start = 50
                files_progress_end = 70
                files_progress_range = files_progress_end - files_progress_start

                
                
                if fixed_data and fixed_data == 'claimrequest':
                    print(f"Claim request found:")
                    # Generate claim documents (70-90%)
                    claim_result = generate_claim_document_pdf_task(
                        communication_ids,
                        instance.id,
                        progress_recorder=progress_recorder,
                        progress_start=70,
                        progress_end=90,
                        claim_id=fixed_data_id,
                        attach_claim_documents=attach_claim_documents
                    )
                elif fixed_data and fixed_data == 'sepa_payments':
                    print(f"sepa_payments found:")
                    # Generate sepa_payments documents (70-90%)
                    billing_result = generate_sepa_payments_document_pdf_task(
                        communication_ids, 
                        instance.id,
                        progress_recorder=progress_recorder,
                        progress_start=70,
                        progress_end=90,
                        sepa_remittance_id=fixed_data_id
                    )
                else:
                    print(f"No claim request found")
                
                    """ if attach_letter:
                        for i, comm_file in enumerate(created_files):
                            n_file = get_communication_file(comm_file.id)
                            if n_file:
                                comm_file.file = n_file
                                comm_file.save() """
                                
                    progress_recorder.set_progress(
                        100, 
                        100, 
                        description=f"Fitxers generats"
                    )
                
                # Les cartes pendents es renderitzen aqui, un cop els passos anteriors
                # ja han adjuntat les factures a les comunicacions.
                render_pending_letter_files(communication_ids)
                    
            except Exception as e:
                print(f"Error generating files and claim documents: {str(e)}")
                progress_recorder.set_progress(90, 100, description=f"Error en generació de fitxers: {str(e)}")
        status_coms = CommunicationProcessStatus.objects.get(
            token=ConfigProject.objects.get(token='communication_process_status_files_created_token').value
        )
        default_status = CommunicationProcessStatus.objects.get(is_default=True)
        LogCommunicationProcessStatusChange.objects.create(
            object=instance,
            previous_status=instance.status,
            current_status=status_coms if all_com_files_created else default_status,
            user=user,
        )
        instance.status = status_coms if all_com_files_created else default_status
        instance.save()
        with translation.override(settings.LANGUAGE_CODE):
            progress_recorder.set_progress(90, 100, description=_("No communications to process"))
            progress_recorder.set_progress(90, 100, description=_("Finishing process"))
            notification_save = {
                'token': uuid.uuid4(),
                'name': _("Communication process completed"),
                'description': _("Communication process %(token)s completed successfully") % {"token": instance.token},
                'module': 'communication',
                'entity': 'process-communications',
                'object_id': None,
                'is_active': True
            }
            progress_finished_desc = _("Process finished")
        Notification.objects.create(**notification_save)
        progress_recorder.set_progress(100, 100, description=progress_finished_desc)
        
        return {
            "status": "success",
            "process_id": process_id,
            "all_files_created": all_com_files_created,
            "message": "Communication process completed successfully"
        }
        
    except Exception as e:
        # Update status to error or default on failure
        try:
            instance = CommunicationProcess.objects.get(id=process_id)
            status_default = CommunicationProcessStatus.objects.get(is_default=True)
            instance.status = status_default
            instance.save()
        except:
            pass
        return {"status": "error", "message": str(e)} 


@shared_task(bind=True)
def update_communication_messages_task(self, message_id, process_id, type_id):
    progress_recorder = ProgressRecorder(self)
    
    try:
        process = CommunicationProcess.objects.get(id=process_id)
        message = Message.objects.get(id=message_id)
        type_instance = MessageType.objects.get(id=type_id)
        
        communications = message.communications.all()
        total_communications = communications.count()
        
        if total_communications == 0:
            progress_recorder.set_progress(0, 1, description="No communications to update")
            return {
                "status": "success",
                "message": "Message updated successfully",
                "task_id": self.request.id,
                "total_communications": 0
            }
        
        progress_recorder.set_progress(0, total_communications, description="Actualitzant comunicacions")
        
        i = 0
        for comm in communications:
            updated_msg = comm.messages.get(type=type_instance)
            comm.messages.remove(updated_msg)
            comm.messages.add(message)
            comm.save()
            if 'email' in comm.type_tokens.split(','):
                create_email_template(comm)
            
            i += 1
            progress_recorder.set_progress(
                i, 
                total_communications, 
                description=f"Actualitzant comunicacions ({i}/{total_communications})"
            )
        process.updating_messages_task_id = None
        process.save()
        process.refresh_from_db()
        return {
            "status": "success",
            "message": "Message updated successfully",
            "task_id": self.request.id,
            "total_communications": total_communications
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "task_id": self.request.id
        } 


@shared_task
def get_communication_process_data(request_data):
    import time
    from communication.views.manage_communication_process_view import (
        filter_by_address,
        filter_by_billing,
        filter_by_claim_request,
        filter_by_communication,
        filter_by_contract,
        filter_by_contract_request,
        filter_by_draft,
        filter_by_fixed_billing,
        filter_by_person,
        filter_by_sepa_remittance,
        filter_by_supply_cut,
        filter_by_supply_point,
    )

    filter_type = request_data.get('type', None)
    filter_data = request_data.get('filters', None)
    group_same = request_data.get('group_same', [])

    persons = []
    time_start = time.time()

    if filter_type == 'CONTRACT':
        persons = filter_by_contract(filter_data, group_same)
    elif filter_type == 'BILLING':
        persons = filter_by_billing(filter_data, group_same)
    elif filter_type == 'CONTRACTREQUEST':
        persons = filter_by_contract_request(filter_data, group_same)
    elif filter_type == 'ADDRESS':
        persons = filter_by_address(filter_data, group_same)
    elif filter_type == 'PERSON':
        persons = filter_by_person(filter_data, group_same)
    elif filter_type == 'SUPPLYPOINT':
        persons = filter_by_supply_point(filter_data, group_same)
    elif filter_type == 'SUPPLYCUT':
        persons = filter_by_supply_cut(filter_data, group_same)
    elif filter_type == 'COMMUNICATION':
        persons = filter_by_communication(filter_data, group_same)
    elif filter_type == 'DRAFT':
        persons = filter_by_draft(filter_data, group_same)
    elif filter_type == 'FIXED':
        # Un objecte fixat sempre ha de resoldre's. Si l'entitat no es coneix, la
        # tasca falla en lloc de deixar `persons` buit: una llista buida era
        # indistingible de "no hi ha destinataris" al wizard.
        fixed_filters = {
            'billing': filter_by_fixed_billing,
            'claimrequest': filter_by_claim_request,
            'sepa_payments': filter_by_sepa_remittance,
            'supplycut': filter_by_supply_cut,
        }
        entity = (filter_data or {}).get('entity', None)
        fixed_filter = fixed_filters.get(entity, None)
        if fixed_filter is None:
            raise ValueError(f"Unknown fixed_data entity: {entity!r}")
        persons = fixed_filter(filter_data, group_same)

    time_end = time.time()
    print(f"Time taken: {time_end - time_start} seconds")
    return {"persons": persons}


COMMUNICATION_EXPORT_COLUMNS = {
    "id": (gettext_lazy("ID"), lambda c: c.id),
    "token": (gettext_lazy("Token"), lambda c: c.token or ''),
    "process_token": (gettext_lazy("Process Token"), lambda c: c.process.token if c.process else ''),
    "person_name": (gettext_lazy("Person Name"), lambda c: f"{c.person.name} {c.person.surname or ''}".strip() if c.person else ''),
    "person_token": (gettext_lazy("Person Token"), lambda c: c.person.token if c.person else ''),
    "status": (gettext_lazy("Status"), lambda c: c.status.name if c.status else ''),
    "used_email": (gettext_lazy("Used Email"), lambda c: c.used_email or ''),
    "used_phones": (gettext_lazy("Used Phones"), lambda c: c.used_phones or ''),
    "created_at": (gettext_lazy("Created At"), lambda c: c.created_at.strftime('%Y-%m-%d %H:%M:%S') if c.created_at else ''),
    "sent_at": (gettext_lazy("Sent At"), lambda c: c.sent_at.strftime('%Y-%m-%d %H:%M:%S') if c.sent_at else ''),
    "type_names": (gettext_lazy("Type Names"), lambda c: c.type_names or ''),
    "use_type": (gettext_lazy("Use Type"), lambda c: c.use_type.name if c.use_type else ''),
}
COMMUNICATION_EXPORT_DEFAULT_COLUMNS = [
    "id", "token", "process_token", "person_name", "person_token", "status",
    "used_email", "used_phones", "created_at", "sent_at", "type_names", "use_type",
]


@shared_task
def export_communications_csv_task(query_params):
    try:
        from communication.filters.communication_filter import CommunicationFilter
        from documentmanager.utils.generic_export_service import (
            build_export_csv_bytes, parse_columns_param, resolve_columns,
        )

        base_queryset = Communication.objects.all().order_by('-created_at', '-status', '-sent_at')
        filterset = CommunicationFilter(data=query_params, queryset=base_queryset)
        queryset = filterset.qs.select_related('person', 'status', 'process', 'use_type')

        ordering = (query_params or {}).get('ordering')
        if ordering:
            queryset = queryset.order_by(*[o.strip() for o in ordering.split(',') if o.strip()])

        columns = resolve_columns(
            COMMUNICATION_EXPORT_COLUMNS,
            COMMUNICATION_EXPORT_DEFAULT_COLUMNS,
            parse_columns_param(query_params),
        )
        csv_bytes = build_export_csv_bytes(queryset, columns)
        filename = f"communications_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        service = settings.DOCUMENT_MANAGER_SERVICES.get("communication", "hdd")
        document = upload_document(
            file=ContentFile(csv_bytes, name=filename),
            entity="COMMUNICATION",
            field="EXPORT",
            entity_id=0,
            entity_token="COMMUNICATION_EXPORT",
            folder="",
            service=service,
            document_name=filename,
            date=timezone.now(),
        )

        return {
            "status": "success",
            "message": "Communications export generated successfully",
            "document_id": document.id,
            "document_name": filename,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating communications export: {str(e)}",
        }