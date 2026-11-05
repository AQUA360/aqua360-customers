from celery.result import AsyncResult
from django.db import transaction

from billing.models import Reading, ReadingBatch, ReadingBatchStatus, ReadingDocument
from billing.utils.reading_filters import PENDING_READING_FILTER
from coredata.models import ConfigProject


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
    try:
        reading_batch = ReadingBatch.objects.select_related('status').get(id=batch_id)
    except ReadingBatch.DoesNotExist:
        raise ReturnToPendingError("Reading batch not found", 404)

    pending_processing_token = ConfigProject.objects.get(token='reading_batch_pending_processing_token').value
    pending_token = ConfigProject.objects.get(token='reading_batch_pending_token').value

    if not reading_batch.status or reading_batch.status.token != pending_processing_token:
        raise ReturnToPendingError("El lot no està pendent de processar.", 409)

    existing_task_id = reading_batch.assign_readings_task_id
    if existing_task_id:
        task_result = AsyncResult(existing_task_id)
        if task_result.state in ['PENDING', 'STARTED', 'PROGRESS']:
            raise ReturnToPendingError("Encara s'estan assignant lectures a aquest lot.", 409)

    assigned_readings = Reading.objects.filter(
        batch=reading_batch,
        is_control=False,
    ).filter(PENDING_READING_FILTER).distinct().count()
    if assigned_readings > 0:
        raise ReturnToPendingError("No es pot tornar enrere: el lot ja té lectures assignades.", 409)

    pending_status = ReadingBatchStatus.objects.get(token=pending_token)
    with transaction.atomic():
        reading_batch.status = pending_status
        reading_batch.assign_readings_task_id = None
        reading_batch.save(update_fields=['status', 'assign_readings_task_id'])
        # L'assignació buida deixa els documents lligats al lot; es desvinculen
        # perquè es puguin tornar a fer servir en tornar a configurar-lo.
        ReadingDocument.objects.filter(batch=reading_batch).update(batch=None)

    reading_batch.refresh_from_db()
    return reading_batch
