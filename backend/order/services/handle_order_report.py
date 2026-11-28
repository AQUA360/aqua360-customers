import requests
import logging
from datetime import datetime, date
from urllib.parse import urlsplit
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from order.models import OrderReport, OrderReportDocument, Operator
from got.models import OrderFormSubmission
from documentmanager.models import Document
from documentmanager.utils.main_utils import upload_document
from coredata.utils.name_utils import generate_token
from order.utils.upload_rules import MAX_UPLOAD_BYTES, UploadRejected, clean_text, resolve_gmao_url, valid_username, validate_file

logger = logging.getLogger(__name__)

host = settings.GMAO_HOST

# Límits del que pot portar un missatge del GMAO
MAX_REPORTS = 50
MAX_PHOTOS = 20
MAX_FORM_FIELDS = 100
MAX_TOKEN_LENGTH = 100
MAX_NAME_LENGTH = 100
MAX_TEXT_LENGTH = 5000

def _download_and_upload_document(url, entity, field, entity_id, entity_token):
    """
    Download a file from GMAO host and upload it to document manager.

    Només es baixen fitxers del servidor del GMAO (el missatge no pot apuntar a una altra
    adreça), sense seguir redireccions, i només imatges i PDF de mida limitada.
    """
    if not url:
        return None

    full_url = resolve_gmao_url(url, host)
    if not full_url:
        logger.warning("Fitxer del GMAO descartat: l'adreça no és del servidor del GMAO.")
        return None

    try:
        with requests.get(full_url, timeout=10, stream=True, allow_redirects=False) as response:
            response.raise_for_status()
            declared_size = int(response.headers.get('Content-Length') or 0)
            if declared_size > MAX_UPLOAD_BYTES:
                logger.warning("Fitxer del GMAO descartat: supera la mida màxima (%s bytes).", declared_size)
                return None
            chunks = []
            total = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    logger.warning("Fitxer del GMAO descartat: supera la mida màxima.")
                    return None
                chunks.append(chunk)
        data = b''.join(chunks)

        file_name = validate_file(urlsplit(full_url).path, data[:16], len(data))
        content = ContentFile(data)

        service = settings.DOCUMENT_MANAGER_SERVICES.get("order", "hdd")

        document = upload_document(
            file=content,
            entity=entity,
            field=field,
            entity_id=entity_id,
            entity_token=entity_token,
            folder="",
            service=service,
            document_name=file_name
        )
        return document
    except UploadRejected as e:
        logger.warning("Fitxer del GMAO descartat: %s", e)
        return None
    except Exception as e:
        logger.error("Error downloading/uploading document from %s: %s", full_url, e)
        return None

def process_gmao_order_report(order, reports_payload):
    """
    Process reports from GMAO and create OrderReport, OrderFormSubmission and Documents.
    """
    results = []

    if not isinstance(reports_payload, list):
        logger.warning("GMAO reports ignorats: no són una llista.")
        return results
    if len(reports_payload) > MAX_REPORTS:
        logger.warning("GMAO reports: %s informes, només es processen els %s primers.", len(reports_payload), MAX_REPORTS)
        reports_payload = reports_payload[:MAX_REPORTS]

    for report_data in reports_payload:
        if not isinstance(report_data, dict):
            logger.warning("Report no vàlid (no és un objecte), skipping ...")
            continue
        username = report_data.get("username")
        if not valid_username(username):
            logger.warning("Report missing or invalid username, skipping ...")
            continue
            
        # Get or create Operator
        operator_token = f"GMAO_{username}"
        operator, created = Operator.objects.get_or_create(
            token=operator_token,
            defaults={
                "name": clean_text(report_data.get("user_first_name"), MAX_NAME_LENGTH),
                "surname": clean_text(report_data.get("user_last_name"), MAX_NAME_LENGTH),
                "is_active": True
            }
        )
        
        if created:
            logger.info(f"Created new operator from GMAO report: {operator_token}")
        
        #  Parse times and calculate duration
        start_at_str = report_data.get("start_at")
        end_at_str = report_data.get("end_at")
        
        start_dt = None
        end_dt = None
        start_time = None
        end_time = None
        report_date = date.today()
        time_dedicated = 0
        
        try:
            if start_at_str:
                # fromisoformat handles +00:00, but replace Z for older python versions if needed
                start_dt = datetime.fromisoformat(start_at_str.replace('Z', '+00:00'))
                start_time = start_dt.time()
                report_date = start_dt.date()
            
            if end_at_str:
                end_dt = datetime.fromisoformat(end_at_str.replace('Z', '+00:00'))
                end_time = end_dt.time()
                
            if start_dt and end_dt:
                time_dedicated = int((end_dt - start_dt).total_seconds() / 60)
        except Exception as e:
            logger.error(f"Error parsing dates in report for operator {operator_token}: {e}")

        #  Create OrderReport
        try:
            order_report_token = report_data.get("report_token")
            if not isinstance(order_report_token, str) or not order_report_token.strip() or len(order_report_token) > MAX_TOKEN_LENGTH:
                order_report_token = generate_token(OrderReport)
            check_existing = OrderReport.objects.filter(token=order_report_token).exists()
            if check_existing:
                logger.warning(f"OrderReport with token {order_report_token} already exists, skipping creation.")
                continue
            with transaction.atomic():
                order_report = OrderReport.objects.create(
                    order=order,
                    operator=operator,
                    start_at=start_time,
                    end_at=end_time,
                    time_dedicated=max(0, time_dedicated),
                    report_date=report_date,
                    observation=clean_text(report_data.get("description"), MAX_TEXT_LENGTH),
                    token=order_report_token
                )

                #  Handle general photos (OrderReportDocument)
                photos = report_data.get("photos", [])
                if not isinstance(photos, list):
                    photos = []
                for photo_url in photos[:MAX_PHOTOS]:
                    # Using entity "ORDER_REPORT" as per general requirement
                    document = _download_and_upload_document(
                        photo_url, 
                        entity="ORDER_REPORT", 
                        field="report_photo", 
                        entity_id=order_report.id, 
                        entity_token=order_report.token
                    )
                    if document:
                        OrderReportDocument.objects.create(
                            order_report=order_report,
                            file=document,
                            token=generate_token(OrderReportDocument)
                        )
                
                #  Handle form submission
                form_submission_data = report_data.get("form_submission")
                if isinstance(form_submission_data, list):
                    form_submission_data = [
                        item for item in form_submission_data[:MAX_FORM_FIELDS]
                        if isinstance(item, dict) and isinstance(item.get("token"), str)
                        and 0 < len(item["token"]) <= MAX_TOKEN_LENGTH
                    ]
                else:
                    form_submission_data = None
                if form_submission_data:
                    processed_form = []
                    new_doc_ids = []
                    
                    for field in form_submission_data:
                        token = field.get("token")
                        response = field.get("response")
                        field_type = field.get("type")

                        # Photo fields are declared by type; fall back to the path heuristic
                        # for payloads published before GMAO started sending the field type.
                        is_photo = field_type == "photo" or (
                            not field_type and isinstance(response, str) and response.startswith("/")
                        )
                        if is_photo and isinstance(response, str) and response:
                            document = _download_and_upload_document(
                                response,
                                entity="ORDER_FORM_SUBMISSION_PENDING", # Temporary entity
                                field=token,
                                entity_id=order.id, 
                                entity_token=order.token
                            )
                            if document:
                                response = str(document.id)
                                new_doc_ids.append(document.id)
                        
                        processed_form.append({
                            "token": token,
                            "name": field.get("name") or token,
                            "type": field_type or ("photo" if is_photo else "text"),
                            "required": field.get("required", False),
                            "response": response
                        })
                    
                    # Create OrderFormSubmission
                    submission = OrderFormSubmission.objects.create(
                        order_report=order_report,
                        filled_form=processed_form
                    )
                    
                    # Update document entity and entity_id to the actual submission
                    if new_doc_ids:
                        Document.objects.filter(id__in=new_doc_ids).update(
                            entity="ORDER_FORM_SUBMISSION",
                            entity_id=submission.id
                        )

                results.append(order_report.id)
                logger.info(f"Successfully processed report for {operator_token}, OrderReport ID: {order_report.id}")
                
        except Exception as e:
            logger.error(f"Failed to process report for {operator_token}: {e}", exc_info=True)
            
    return results
