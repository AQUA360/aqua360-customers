from unittest.mock import patch

from django.test import TestCase

from billing.models import ReadingBatch
from billing.tasks import estimate_readings_task


class EstimateReadingsTaskCleanupTests(TestCase):
    """Una estimació que falla abans del seu try no ha de deixar el lot bloquejat."""

    def setUp(self):
        self.batch = ReadingBatch.objects.create(name='Lot', estimating_task_id='task-1')

    @patch('billing.tasks._run_estimate_readings', side_effect=RuntimeError('boom'))
    def test_error_inicial_allibera_el_task_id(self, _run):
        result = estimate_readings_task.apply(args=[self.batch.id], task_id='task-1', throw=False)

        self.assertTrue(result.failed())
        self.batch.refresh_from_db()
        self.assertIsNone(self.batch.estimating_task_id)

    @patch('billing.tasks._run_estimate_readings', side_effect=RuntimeError('boom'))
    def test_no_toca_una_estimacio_posterior(self, _run):
        self.batch.estimating_task_id = 'task-2'
        self.batch.save(update_fields=['estimating_task_id'])

        estimate_readings_task.apply(args=[self.batch.id], task_id='task-1', throw=False)

        self.batch.refresh_from_db()
        self.assertEqual(self.batch.estimating_task_id, 'task-2')
