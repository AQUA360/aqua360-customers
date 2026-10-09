"""
Cua general de descàrregues (`ExportJob`).

Ús des d'una vista que avui fa `task.delay(...)` i retorna `{task_id}`:

    job = enqueue_export(request, export_readings_task, kind="readings",
                         name="Lectures", args=[reading_ids], kwargs={"columns": columns})
    return Response(export_job_response(job), status=202)

La resposta conserva `task_id`, de manera que els frontals que encara fan
polling a `/task-progress/<task_id>/` continuen funcionant, i hi afegeix
`export_job_id` perquè el frontal la pugui seguir des del panell de descàrregues.
"""
import os
import uuid

from django.db import transaction
from django.utils import timezone

from documentmanager.models import ExportJob


def enqueue_export(request, task, *, kind, name, args=None, kwargs=None, params=None):
    """
    Crea l'ExportJob i despatxa la tasca amb un task_id generat aquí, perquè la
    fila existeixi abans que el worker l'agafi (els signals la busquen per task_id).
    """
    user = getattr(request, "user", None)
    task_id = str(uuid.uuid4())
    job = ExportJob.objects.create(
        requested_by=user if user is not None and user.is_authenticated else None,
        kind=kind,
        name=(name or kind)[:255],
        params=params or {},
        task_id=task_id,
    )
    transaction.on_commit(lambda: task.apply_async(args=args or [], kwargs=kwargs or {}, task_id=task_id))
    return job


def export_job_response(job, message=None):
    return {
        "task_id": job.task_id,
        "export_job_id": job.id,
        "status": "pending",
        "message": message or f"{job.name} export in progress",
    }


def mark_job_running(task_id):
    ExportJob.objects.filter(task_id=task_id, status=ExportJob.STATUS_PENDING).update(
        status=ExportJob.STATUS_RUNNING, started_at=timezone.now(),
    )


def finish_job(job, state, result):
    """
    Desa el resultat final d'una tasca a l'ExportJob.

    `state` és l'estat de Celery (SUCCESS/FAILURE/REVOKED) i `result` el valor
    retornat (o l'excepció). Moltes tasques capturen les seves excepcions i
    retornen `{"status": "error"}` amb estat SUCCESS: també es tracten com a error.
    """
    if not job.is_active:
        # Cancel·lada (o ja tancada) mentre corria: no la reobrim.
        return job

    now = timezone.now()
    job.completed_at = now
    if job.started_at is None:
        job.started_at = now

    if state != "SUCCESS":
        job.status = ExportJob.STATUS_FAILED
        job.error_message = str(result) if result is not None else state
    elif isinstance(result, dict) and result.get("status") in ("error", "failed", "failure", "warning"):
        # "warning": l'informe no s'ha pogut generar per un motiu conegut (p. ex. sense dades).
        job.status = ExportJob.STATUS_FAILED
        job.error_message = result.get("message") or result.get("error") or "Error"
    else:
        data = result if isinstance(result, dict) else {}
        job.status = ExportJob.STATUS_COMPLETED
        job.document_id = data.get("document_id") or None
        job.file_url = data.get("file_url") or None
        job.file_name = (
            data.get("document_name")
            or data.get("filename")
            or data.get("file_name")
            or (os.path.basename(job.file_url.split("?")[0]) if job.file_url else None)
        )
        if not job.document_id and not job.file_url:
            job.status = ExportJob.STATUS_FAILED
            job.error_message = "The task finished without returning a file"

    job.save(update_fields=[
        "status", "error_message", "document", "file_url", "file_name", "started_at", "completed_at",
    ])
    return job


def reconcile_job(job):
    """
    Xarxa de seguretat per si el signal de final no ha arribat (worker reiniciat,
    tasca acabada abans de desplegar els signals...): consulta el resultat de
    Celery i, si ja és definitiu, el desa.
    """
    if not job.is_active or not job.task_id:
        return job
    from celery.result import AsyncResult

    res = AsyncResult(job.task_id)
    if res.state in ("SUCCESS", "FAILURE", "REVOKED"):
        return finish_job(job, res.state, res.result)
    if res.state == "STARTED" and job.status == ExportJob.STATUS_PENDING:
        mark_job_running(job.task_id)
        job.refresh_from_db()
    return job


def cancel_job(job):
    from customers.queue_utils import revoke_queue_task

    revoke_queue_task(job.task_id)
    job.status = ExportJob.STATUS_CANCELLED
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "completed_at"])
    return job
