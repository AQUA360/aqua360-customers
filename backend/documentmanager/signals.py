"""
Manté l'estat dels ExportJob a partir del cicle de vida de les tasques de Celery,
sense haver de tocar cap tasca: si el task_id que comença o acaba té una fila a
la cua de descàrregues, s'actualitza.
"""
import logging

from celery.signals import task_postrun, task_prerun

logger = logging.getLogger(__name__)


@task_prerun.connect
def export_job_task_prerun(sender=None, task_id=None, **kwargs):
    from documentmanager.utils.export_jobs import mark_job_running

    try:
        mark_job_running(task_id)
    except Exception:
        logger.exception("No s'ha pogut marcar l'ExportJob de la tasca %s com a en curs", task_id)


@task_postrun.connect
def export_job_task_postrun(sender=None, task_id=None, retval=None, state=None, **kwargs):
    from documentmanager.models import ExportJob
    from documentmanager.utils.export_jobs import finish_job

    try:
        job = ExportJob.objects.filter(task_id=task_id).first()
        if job is not None:
            finish_job(job, state, retval)
    except Exception:
        logger.exception("No s'ha pogut tancar l'ExportJob de la tasca %s", task_id)
