from celery.result import AsyncResult
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from billing.models import ReadingBatch
from billing.utils.reading_batch_return import IN_PROGRESS_TASK_STATES


class Command(BaseCommand):
    help = (
        'Clear a legacy estimation ID only after independently confirming that it '
        'has finished (worker logs or execution records). PENDING, age, and an '
        'empty worker inspection alone cannot distinguish expired results from '
        'queued work. Do not run while legacy workers may still execute this ID.'
    )

    def add_arguments(self, parser):
        parser.add_argument('batch_id', type=int)
        parser.add_argument('task_id')
        parser.add_argument('--confirmed-finished', action='store_true')

    def handle(self, *args, **options):
        if not options['confirmed_finished']:
            raise CommandError('Independent completion evidence requires --confirmed-finished.')
        with transaction.atomic():
            try:
                batch = ReadingBatch.objects.select_for_update().get(pk=options['batch_id'])
            except ReadingBatch.DoesNotExist:
                raise CommandError('Reading batch not found.')
            if batch.estimating_task_id != options['task_id']:
                raise CommandError('Task ID does not match the current estimation.')
            if batch.estimating_task_status is not None:
                raise CommandError('Only legacy estimations with unknown lifecycle can be reconciled.')
            state = AsyncResult(options['task_id']).state
            if state in IN_PROGRESS_TASK_STATES and state != 'PENDING':
                raise CommandError('Celery still reports an active estimation.')
            batch.estimating_task_id = None
            batch.estimating_task_status = 'FINISHED'
            batch.save(update_fields=['estimating_task_id', 'estimating_task_status'])
        self.stdout.write(self.style.SUCCESS('Legacy estimation reconciled.'))
