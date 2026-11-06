from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
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
