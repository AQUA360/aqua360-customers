from celery.result import AsyncResult
from django.db import transaction

from billing.models import Reading, ReadingBatch, ReadingBatchStatus, ReadingDocument
from billing.utils.reading_filters import PENDING_READING_FILTER
from coredata.models import ConfigProject


IN_PROGRESS_TASK_STATES = ('PENDING', 'RECEIVED', 'STARTED', 'PROGRESS', 'RETRY')


class ReturnToPendingError(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def return_reading_batch_to_pending(batch_id):
    """
    Torna un lot del pas de lectures (Pendent de processar) al pas de
    configuració (Pendent) quan no hi ha cap lectura pendent assignada.
    """
    pending_processing_token = ConfigProject.objects.get(token='reading_batch_pending_processing_token').value
    pending_token = ConfigProject.objects.get(token='reading_batch_pending_token').value
    pending_status = ReadingBatchStatus.objects.get(token=pending_token)

    with transaction.atomic():
        # Bloqueig de fila: serialitza amb l'inici d'una assignació o estimació
        # (que també bloquegen el lot abans de desar-ne el task_id).
        try:
            # of=('self',): status és nullable i select_related fa un LEFT JOIN.
            # PostgreSQL no admet FOR UPDATE sobre el costat nul d'un outer join.
            reading_batch = (
                ReadingBatch.objects.select_for_update(of=('self',))
                .select_related('status')
                .get(id=batch_id)
            )
        except ReadingBatch.DoesNotExist:
            raise ReturnToPendingError("Reading batch not found", 404)

        if not reading_batch.status or reading_batch.status.token != pending_processing_token:
            raise ReturnToPendingError("El lot no està pendent de processar.", 409)

        if _task_in_progress(reading_batch.assign_readings_task_id):
            raise ReturnToPendingError("Encara s'estan assignant lectures a aquest lot.", 409)

        if estimation_in_progress(reading_batch):
            raise ReturnToPendingError("Encara s'estan estimant lectures en aquest lot.", 409)

        assigned_readings = Reading.objects.filter(
            batch=reading_batch,
            is_control=False,
        ).filter(PENDING_READING_FILTER).distinct().count()
        if assigned_readings > 0:
            raise ReturnToPendingError("No es pot tornar enrere: el lot ja té lectures assignades.", 409)

        reading_batch.status = pending_status
        reading_batch.assign_readings_task_id = None
        reading_batch.estimating_task_id = None
        reading_batch.estimating_task_status = None
        reading_batch.save(update_fields=[
            'status', 'assign_readings_task_id', 'estimating_task_id', 'estimating_task_status',
        ])
        # L'assignació buida deixa els documents lligats al lot; es desvinculen
        # perquè es puguin tornar a fer servir en tornar a configurar-lo.
        ReadingDocument.objects.filter(batch=reading_batch).update(batch=None)

    reading_batch.refresh_from_db()
    return reading_batch


def _task_in_progress(task_id):
    if not task_id:
        return False
    return AsyncResult(task_id).state in IN_PROGRESS_TASK_STATES


def estimation_in_progress(batch):
    if not batch.estimating_task_id:
        return False
    # This evidence survives Celery result expiry. Unknown legacy PENDING IDs
    # must be reconciled explicitly; age or an empty worker inspection is not
    # proof that a task cannot still run.
    if batch.estimating_task_status == 'FINISHED':
        return False
    if batch.estimating_task_status in ('QUEUED', 'RUNNING'):
        return True
    return _task_in_progress(batch.estimating_task_id)
