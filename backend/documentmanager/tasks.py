from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from documentmanager.utils.main_utils import upload_document


@shared_task
def generic_export_task(entity, query_params):
    from documentmanager.utils.export_registry import get_export_config
    from documentmanager.utils.generic_export_service import build_export_xlsx_bytes, apply_ordering, parse_columns_param

    try:
        config = get_export_config(entity)
        if config is None:
            return {"status": "error", "message": f"Unknown export entity: {entity}"}

        queryset = config.filterset_class(data=query_params, queryset=config.queryset()).qs
        queryset = apply_ordering(queryset, query_params, config.default_ordering)

        columns = config.resolve_columns(parse_columns_param(query_params))

        file_bytes = build_export_xlsx_bytes(queryset, columns)
        filename = f"{entity}_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        service = settings.DOCUMENT_MANAGER_SERVICES.get(config.service_key or entity, "hdd")

        document = upload_document(
            file=ContentFile(file_bytes, name=filename),
            entity=config.document_entity,
            field="EXPORT",
            entity_id=0,
            entity_token=f"{config.document_entity}_EXPORT",
            folder="",
            service=service,
            document_name=filename,
            date=timezone.now(),
        )

        return {
            "status": "success",
            "message": f"{entity} export generated successfully",
            "document_id": document.id,
            "document_name": filename,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating {entity} export: {str(e)}",
        }


# Dies que es conserven les files de la cua de descàrregues (ExportJob).
EXPORT_JOB_RETENTION_DAYS = 30
# Una descàrrega "en curs" durant més d'aquestes hores es dona per perduda
# (worker reiniciat o tasca matada sense passar pel signal de final).
EXPORT_JOB_STALE_HOURS = 12


@shared_task
def cleanup_export_jobs():
    from datetime import timedelta
    from documentmanager.models import ExportJob
    from documentmanager.utils.export_jobs import reconcile_job

    now = timezone.now()
    for job in ExportJob.objects.filter(status__in=ExportJob.ACTIVE_STATUSES,
                                        created_at__lt=now - timedelta(hours=EXPORT_JOB_STALE_HOURS)):
        job = reconcile_job(job)
        if job.is_active:
            job.status = ExportJob.STATUS_FAILED
            job.error_message = "Timed out"
            job.completed_at = now
            job.save(update_fields=["status", "error_message", "completed_at"])

    deleted, _ = ExportJob.objects.filter(created_at__lt=now - timedelta(days=EXPORT_JOB_RETENTION_DAYS)).delete()
    return {"deleted": deleted}
