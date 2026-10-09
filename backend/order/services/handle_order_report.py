import requests
import logging
from datetime import datetime, date
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from order.models import OrderReport, OrderReportDocument, Operator
from got.models import OrderFormSubmission
from documentmanager.models import Document
from documentmanager.utils.main_utils import upload_document
from coredata.utils.name_utils import generate_token

logger = logging.getLogger(__name__)

host = settings.GMAO_HOST

def _download_and_upload_document(url, entity, field, entity_id, entity_token):
    """
    Download a file from GMAO host and upload it to document manager.
    """
    if not url:
        return None
    
    if url.startswith('http://') or url.startswith('https://'):
        full_url = url
    else:
        #  host doesn't end with slash and url doesn't start with slash
        clean_host = host.rstrip('/')
        clean_url = url.lstrip('/')
        if not clean_host:
            full_url = clean_url  # If host is not set, use the URL as is (assuming it's absolute)
        else:
            full_url = f"{clean_host}/{clean_url}"
    
    try:
        response = requests.get(full_url, timeout=10)
        response.raise_for_status()
        
        file_name = full_url.split('/')[-1]
        content = ContentFile(response.content)
        
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
    except Exception as e:
        logger.error(f"Error downloading/uploading document from {full_url}: {e}")
        return None

def process_gmao_order_report(order, reports_payload):
    """
    Process reports from GMAO and create OrderReport, OrderFormSubmission and Documents.
    """
    results = []
    
    for report_data in reports_payload:
        username = report_data.get("username")
        if not username:
            logger.warning("Report missing username, skipping ...")
            continue
            
        # Get or create Operator
        operator_token = f"GMAO_{username}"
        operator, created = Operator.objects.get_or_create(
            token=operator_token,
            defaults={
                "name": report_data.get("user_first_name", ""),
                "surname": report_data.get("user_last_name", ""),
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
            order_report_token = report_data.get("report_token", generate_token(OrderReport))
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
                    observation=report_data.get("description", ""),
                    token=order_report_token
                )

                #  Handle general photos (OrderReportDocument)
                photos = report_data.get("photos", [])
                for photo_url in photos:
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
