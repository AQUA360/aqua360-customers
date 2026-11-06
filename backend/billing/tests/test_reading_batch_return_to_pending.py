from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIRequestFactory, force_authenticate

from billing.models import Reading, ReadingBatch, ReadingBatchStatus, ReadingDocument
from billing.utils.reading_batch_return import ReturnToPendingError, return_reading_batch_to_pending
from billing.views.reading_batch_generate_view import ReadingBatchSummaryView
from coredata.models import ConfigProject


def config_value(token, default_value):
    return ConfigProject.objects.get_or_create(token=token, defaults={'value': default_value})[0].value


def status_for(config_token, default_value, name):
    value = config_value(config_token, default_value)
    return ReadingBatchStatus.objects.get_or_create(token=value, defaults={'name': name})[0]


class ReadingBatchReturnToPendingTests(TestCase):
    """Un lot al pas 3 sense lectures pot tornar a «Pendent» per reconfigurar-lo."""

    def setUp(self):
        self.pending = status_for('reading_batch_pending_token', '1', 'Pendent')
        self.pending_processing = status_for(
            'reading_batch_pending_processing_token', '4', 'Pendent de processar'
        )
        self.batch = ReadingBatch.objects.create(
            name='Lot buit',
            status=self.pending_processing,
        )
        self.document = ReadingDocument.objects.create(batch=self.batch, token='DOC-BUIT')

    def test_sense_lectures_torna_a_pendent_i_desvincula_el_document(self):
        batch = return_reading_batch_to_pending(self.batch.id)

        self.assertEqual(batch.status_id, self.pending.id)
        self.document.refresh_from_db()
        self.assertIsNone(self.document.batch_id)

    def test_amb_lectures_assignades_no_canvia_l_estat(self):
        Reading.objects.create(
            batch=self.batch,
            reading_date=date(2026, 10, 1),
            reading_value=10,
            is_control=False,
        )

        with self.assertRaises(ReturnToPendingError) as caught:
            return_reading_batch_to_pending(self.batch.id)

        self.assertEqual(caught.exception.status_code, 409)
        self.batch.refresh_from_db()
        self.document.refresh_from_db()
        self.assertEqual(self.batch.status_id, self.pending_processing.id)
        self.assertEqual(self.document.batch_id, self.batch.id)

    def test_si_no_esta_pendent_de_processar_no_fa_res(self):
        self.batch.status = self.pending
        self.batch.save(update_fields=['status'])

        with self.assertRaises(ReturnToPendingError) as caught:
            return_reading_batch_to_pending(self.batch.id)

        self.assertEqual(caught.exception.status_code, 409)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status_id, self.pending.id)

    @patch('billing.utils.reading_batch_return.AsyncResult')
    def test_amb_estimacio_en_curs_no_canvia_l_estat(self, async_result):
        async_result.return_value.state = 'STARTED'
        self.batch.estimating_task_id = 'estimate-task'
        self.batch.save(update_fields=['estimating_task_id'])

        with self.assertRaises(ReturnToPendingError) as caught:
            return_reading_batch_to_pending(self.batch.id)

        self.assertEqual(caught.exception.status_code, 409)
        async_result.assert_called_with('estimate-task')
        self.batch.refresh_from_db()
        self.document.refresh_from_db()
        self.assertEqual(self.batch.status_id, self.pending_processing.id)
        self.assertEqual(self.document.batch_id, self.batch.id)

    def _post_return_to_pending(self, *codenames):
        user = get_user_model().objects.create_user(username='lector', password='x')
        user.user_permissions.add(
            *Permission.objects.filter(content_type__app_label='billing', codename__in=codenames)
        )
        request = APIRequestFactory().post(
            f'/billing/reading-batch-summary/{self.batch.id}/return-to-pending/'
        )
        force_authenticate(request, user=user)
        view = ReadingBatchSummaryView.as_view({'post': 'return_to_pending'})
        return view(request, pk=self.batch.id)

    def test_sense_permis_de_canvi_retorna_403(self):
        response = self._post_return_to_pending('add_reading')

        self.assertEqual(response.status_code, 403)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status_id, self.pending_processing.id)

    def test_amb_permis_de_canvi_torna_a_pendent(self):
        response = self._post_return_to_pending('add_reading', 'change_reading')

        self.assertEqual(response.status_code, 200)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status_id, self.pending.id)

    @patch('billing.utils.reading_batch_return.AsyncResult')
    def test_unknown_pending_still_blocks(self, result):
        result.return_value.state = 'PENDING'
        self.batch.estimating_task_id = 'legacy'
        self.batch.save()
        with self.assertRaises(ReturnToPendingError):
            return_reading_batch_to_pending(self.batch.id)

    @patch('billing.utils.reading_batch_return.AsyncResult')
    def test_persistent_active_states_block_even_without_backend_result(self, result):
        result.return_value.state = 'PENDING'
        for state in ('QUEUED', 'RUNNING'):
            with self.subTest(state=state):
                self.batch.estimating_task_id = 'task'
                self.batch.estimating_task_status = state
                self.batch.save()
                with self.assertRaises(ReturnToPendingError):
                    return_reading_batch_to_pending(self.batch.id)
        result.assert_not_called()

    @patch('billing.management.commands.reconcile_finished_estimation.AsyncResult')
    def test_confirmed_legacy_completion_allows_return_after_expiry(self, result):
        result.return_value.state = 'PENDING'
        self.batch.estimating_task_id = 'legacy'
        self.batch.save()
        call_command('reconcile_finished_estimation', self.batch.id, 'legacy', confirmed_finished=True)
        returned = return_reading_batch_to_pending(self.batch.id)
        self.assertEqual(returned.status_id, self.pending.id)

    @patch('billing.management.commands.reconcile_finished_estimation.AsyncResult')
    def test_reconciliation_requires_evidence_and_matching_inactive_legacy_id(self, result):
        self.batch.estimating_task_id = 'legacy'
        self.batch.save()
        with self.assertRaises(CommandError):
            call_command('reconcile_finished_estimation', self.batch.id, 'legacy')
        with self.assertRaises(CommandError):
            call_command('reconcile_finished_estimation', self.batch.id, 'older', confirmed_finished=True)
        for state in ('STARTED', 'PROGRESS', 'RETRY', 'RECEIVED'):
            result.return_value.state = state
            with self.assertRaises(CommandError):
                call_command('reconcile_finished_estimation', self.batch.id, 'legacy', confirmed_finished=True)
        self.batch.estimating_task_status = 'QUEUED'
        self.batch.save()
        with self.assertRaises(CommandError):
            call_command('reconcile_finished_estimation', self.batch.id, 'legacy', confirmed_finished=True)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.estimating_task_id, 'legacy')

    @patch('billing.views.reading_batch_estimate_view.estimate_readings_task.apply_async')
    @patch('billing.views.reading_batch_estimate_view.ContractStatus.objects.get')
    def test_estimation_is_persisted_before_publish_and_prevents_overlap(self, contract_status, publish):
        from types import SimpleNamespace
        from billing.views.reading_batch_estimate_view import ReadingBatchEstimateViewSet

        config_value('contract_active_token', 'active')
        contract_status.return_value.id = 1
        request = SimpleNamespace(data={'supply_points': 'all'})
        view = ReadingBatchEstimateViewSet()
        with self.captureOnCommitCallbacks(execute=True):
            response = view.estimate_readings(request, id=self.batch.id)
            self.assertEqual(response.status_code, 202)
            self.batch.refresh_from_db()
            self.assertEqual(self.batch.estimating_task_status, 'QUEUED')
            self.assertEqual(self.batch.estimating_task_id, response.data['task_id'])
            publish.assert_not_called()
            duplicate = view.estimate_readings(request, id=self.batch.id)
            self.assertEqual(duplicate.status_code, 409)
        publish.assert_called_once()
        self.assertEqual(publish.call_args.kwargs['task_id'], self.batch.estimating_task_id)
