import datetime
from celery import shared_task
from django.utils import timezone

@shared_task
def export_incidents_csv_task(query_params):
    try:
        from notification.models import Incident
        from notification.filters.incident_filter import IncidentFilter
        from notification.utils.incident_csv_export import build_incident_export_csv_bytes
        from documentmanager.utils.main_utils import upload_document
        from django.core.files.base import ContentFile
        from django.conf import settings
        
        # Filter the queryset according to the query_params received
        queryset = Incident.objects.all().order_by('status__position', '-created_at')
        filterset = IncidentFilter(
            data=query_params,
            queryset=queryset,
        )
        filtered = filterset.qs
        
        csv_bytes = build_incident_export_csv_bytes(filtered)
        
        filename = f"incidents_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        service = settings.DOCUMENT_MANAGER_SERVICES.get("statistics", "hdd")
        content_file = ContentFile(csv_bytes, name=filename)
        
        document = upload_document(
            file=content_file,
            entity="INCIDENT",
            field="EXPORT",
            entity_id=0,
            entity_token="INCIDENT_EXPORT",
            folder="",
            service=service,
            document_name=filename,
            date=timezone.now()
        )
        
        return {
            "status": "success",
            "message": "Incidents export generated successfully",
            "document_id": document.id,
            "filename": filename
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating incidents export: {str(e)}"
        }
