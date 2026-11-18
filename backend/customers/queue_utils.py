import logging

logger = logging.getLogger(__name__)


class QueueTaskRevokeError(Exception):
    """No s'ha pogut fer arribar a Celery l'ordre d'aturar una tasca de cua."""


def revoke_queue_task(task_id, related_task_ids=()):
    """
    Mata la tasca de Celery d'un item de cua (BillingQueue/ReportQueue) i, si n'hi ha,
    les seves subtasques (`related_task_ids`), totes amb una sola ordre.

    `terminate=True` amb SIGKILL mata el procés fill del worker (pool prefork) que
    l'està executant; si encara no ha arrencat, el worker la descarta quan li arribi.
    Si el broker no respon es llança `QueueTaskRevokeError`: qui crida no ha de
    marcar l'item com a aturat, perquè la tasca continuaria corrent.
    """
    if not task_id:
        return
    from customers.celery import app as celery_app
    try:
        target = [task_id, *related_task_ids] if related_task_ids else task_id
        celery_app.control.revoke(target, terminate=True, signal='SIGKILL')
    except Exception as e:
        logger.exception("No s'ha pogut revocar la tasca de Celery %s", task_id)
        raise QueueTaskRevokeError(str(e)) from e
