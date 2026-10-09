from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from billing import tasks as billing_tasks
from billing.models import Billing, BillingQueue, BillingStatus
from coredata.models import ConfigProject
from customers.queue_utils import QueueTaskRevokeError
from statistics import tasks as statistics_tasks
from statistics.models import AvailableReport, ReportQueue

REVOKE = 'customers.celery.app.control.revoke'


def billing_status(config_token, default_value):
    """Estat de Billing al qual apunta un ConfigProject (es reaprofita si la BBDD ja el té)."""
    value = ConfigProject.objects.get_or_create(token=config_token, defaults={'value': default_value})[0].value
    return BillingStatus.objects.get_or_create(token=value, defaults={'name': value})[0]


class BillingQueueActionTests(TestCase):
    """Kill/skip/restart de la cua de facturació: la tasca de Celery mor de debò i, si
    sobreviu, no pot trepitjar l'estat de l'item ni engegar res en acabar."""

    def setUp(self):
        self.processing = billing_status('billing_batch_processing', 'Q-PROCESSING')
        self.pending = billing_status('billing_batch_pending', 'Q-PENDING')
        self.processing_documents = billing_status('billing_batch_processing_documents', 'Q-PROCESSING-DOCS')
        self.billing = Billing.objects.create(name='Billing cua', status=self.processing)

        # Cap tasca arriba al broker: només es comprova com s'encuen.
        patcher = mock.patch('celery.app.task.Task.apply_async')
        self.apply_async = patcher.start()
        self.addCleanup(patcher.stop)

    def enqueue(self, task_type='PRE_INVOICE', payload=None):
        item = BillingQueue.objects.create(billing=self.billing, task_type=task_type, payload=payload, status='pending')
        billing_tasks.process_next_queue_item()
        item.refresh_from_db()
        return item

    # --- engegar un item ---------------------------------------------------

    def test_el_task_id_es_desa_abans_d_encuar_la_tasca(self):
        seen = {}

        def check_db(*args, **kwargs):
            # En el moment d'encuar, l'item ja ha de tenir el mateix task_id a la BBDD.
            seen['db_task_id'] = BillingQueue.objects.get(id=item_id).task_id
            seen['task_id'] = kwargs['task_id']

        self.apply_async.side_effect = check_db
        item_id = BillingQueue.objects.create(billing=self.billing, task_type='PRE_INVOICE', status='pending').id
        billing_tasks.process_next_queue_item()

        item = BillingQueue.objects.get(id=item_id)
        self.assertEqual(item.status, 'running')
        self.assertTrue(seen['task_id'])
        self.assertEqual(seen['db_task_id'], seen['task_id'])
        self.assertEqual(item.task_id, seen['task_id'])
        self.billing.refresh_from_db()
        self.assertEqual(self.billing.task_id, seen['task_id'])

    def test_definitive_invoice_rep_els_arguments_del_payload(self):
        payload = {'invoice_ids': [1, 2], 'context': {'base_url': 'x'}, 'issue_date': '2026-10-01',
                   'end_date': '2026-10-31', 'send_at': None}
        item = self.enqueue('DEFINITIVE_INVOICE', payload)
        kwargs = self.apply_async.call_args.kwargs
        self.assertEqual(kwargs['args'], [self.billing.id, [1, 2], {'base_url': 'x'}, '2026-10-01', '2026-10-31', None])
        self.assertEqual(kwargs['kwargs'], {'queue_item_id': item.id})
        self.assertEqual(kwargs['task_id'], item.task_id)

    def test_si_no_es_pot_encuar_queda_failed_i_passa_al_seguent(self):
        self.apply_async.side_effect = [Exception('broker caigut'), None]
        first = BillingQueue.objects.create(billing=self.billing, task_type='PRE_INVOICE', status='pending')
        second = BillingQueue.objects.create(billing=self.billing, task_type='REGENERATE_PDFS', status='pending')
        billing_tasks.process_next_queue_item()
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, 'failed')
        self.assertIn('broker caigut', first.error_message)
        self.assertEqual(second.status, 'running')

    # --- kill / skip / restart --------------------------------------------

    def test_kill_mata_la_tasca_de_celery_i_engega_la_seguent(self):
        item = self.enqueue()
        waiting = BillingQueue.objects.create(billing=self.billing, task_type='REGENERATE_PDFS', status='pending')

        with mock.patch(REVOKE) as revoke:
            billing_tasks.apply_billing_queue_action(item, 'kill')

        revoke.assert_called_once_with(item.task_id, terminate=True, signal='SIGKILL')
        item.refresh_from_db()
        waiting.refresh_from_db()
        self.assertEqual(item.status, 'failed')
        self.assertIsNotNone(item.completed_at)
        self.assertEqual(waiting.status, 'running')

    def test_si_el_revoke_falla_no_es_toca_res(self):
        item = self.enqueue()
        waiting = BillingQueue.objects.create(billing=self.billing, task_type='REGENERATE_PDFS', status='pending')

        with mock.patch(REVOKE, side_effect=ConnectionError('redis no respon')):
            with self.assertRaises(QueueTaskRevokeError):
                billing_tasks.apply_billing_queue_action(item, 'kill')

        item.refresh_from_db()
        waiting.refresh_from_db()
        self.billing.refresh_from_db()
        self.assertEqual(item.status, 'running')
        self.assertEqual(waiting.status, 'pending')
        self.assertEqual(self.billing.status, self.processing)

    def test_un_item_pendent_es_mata_sense_revocar_res(self):
        self.enqueue()  # ocupa la cua
        waiting = BillingQueue.objects.create(billing=self.billing, task_type='REGENERATE_PDFS', status='pending')

        with mock.patch(REVOKE) as revoke:
            billing_tasks.apply_billing_queue_action(waiting, 'skip')

        revoke.assert_not_called()
        waiting.refresh_from_db()
        self.assertEqual(waiting.status, 'skipped')

    def test_kill_de_prefactures_torna_el_billing_a_pendent_de_confirmacio(self):
        item = self.enqueue('PRE_INVOICE')
        with mock.patch(REVOKE):
            billing_tasks.apply_billing_queue_action(item, 'kill')
        self.billing.refresh_from_db()
        self.assertEqual(self.billing.status, self.pending)

    def test_skip_de_definitives_torna_el_billing_a_pendent_de_confirmacio(self):
        self.billing.status = self.processing_documents
        self.billing.save()
        item = self.enqueue('DEFINITIVE_INVOICE', {'invoice_ids': []})
        with mock.patch(REVOKE):
            billing_tasks.apply_billing_queue_action(item, 'skip')
        self.billing.refresh_from_db()
        self.assertEqual(self.billing.status, self.pending)

    def test_kill_d_un_item_ja_acabat_no_toca_el_billing(self):
        item = self.enqueue('PRE_INVOICE')
        BillingQueue.objects.filter(id=item.id).update(status='completed')
        item.refresh_from_db()
        with mock.patch(REVOKE) as revoke:
            billing_tasks.apply_billing_queue_action(item, 'kill')
        revoke.assert_not_called()
        self.billing.refresh_from_db()
        self.assertEqual(self.billing.status, self.processing)

    def test_kill_de_regeneracio_de_pdfs_no_toca_el_billing(self):
        processed = billing_status('billing_batch_processed', 'Q-PROCESSED')
        self.billing.status = processed
        self.billing.save()
        item = self.enqueue('REGENERATE_PDFS')
        with mock.patch(REVOKE):
            billing_tasks.apply_billing_queue_action(item, 'kill')
        self.billing.refresh_from_db()
        self.assertEqual(self.billing.status, processed)

    def test_restart_torna_a_engegar_amb_un_task_id_nou_i_el_billing_en_processant(self):
        item = self.enqueue('PRE_INVOICE')
        with mock.patch(REVOKE):
            billing_tasks.apply_billing_queue_action(item, 'kill')
        old_task_id = item.task_id
        item.refresh_from_db()

        with mock.patch(REVOKE) as revoke:
            billing_tasks.apply_billing_queue_action(item, 'restart')

        revoke.assert_not_called()  # ja no corria
        item.refresh_from_db()
        self.billing.refresh_from_db()
        self.assertEqual(item.status, 'running')
        self.assertNotEqual(item.task_id, old_task_id)
        self.assertEqual(self.billing.status, self.processing)

    # --- la tasca acaba després d'haver-la aturat -------------------------

    def test_una_tasca_que_sobreviu_al_kill_no_trepitja_l_item(self):
        item = self.enqueue()
        with mock.patch(REVOKE):
            billing_tasks.apply_billing_queue_action(item, 'kill')
        waiting = BillingQueue.objects.create(billing=self.billing, task_type='REGENERATE_PDFS', status='pending')

        closed = billing_tasks._close_billing_queue_item(item.id, item.task_id, status='completed')

        self.assertFalse(closed)
        item.refresh_from_db()
        waiting.refresh_from_db()
        self.assertEqual(item.status, 'failed')
        self.assertEqual(waiting.status, 'pending')  # no ha avançat la cua

    def test_la_tasca_antiga_no_tanca_un_item_reiniciat(self):
        item = self.enqueue()
        old_task_id = item.task_id
        with mock.patch(REVOKE):
            billing_tasks.apply_billing_queue_action(item, 'restart')
        item.refresh_from_db()
        self.assertEqual(item.status, 'running')

        self.assertFalse(billing_tasks._close_billing_queue_item(item.id, old_task_id, status='completed'))
        item.refresh_from_db()
        self.assertEqual(item.status, 'running')
        self.assertTrue(billing_tasks._close_billing_queue_item(item.id, item.task_id, status='completed'))
        item.refresh_from_db()
        self.assertEqual(item.status, 'completed')

    def test_la_tasca_real_respecta_un_item_matat(self):
        """regenerate_billing_pdfs executat de debò (sense factures) amb el task_id antic."""
        item = self.enqueue('REGENERATE_PDFS')
        with mock.patch(REVOKE):
            billing_tasks.apply_billing_queue_action(item, 'kill')

        billing_tasks.regenerate_billing_pdfs.apply(
            args=[self.billing.id], kwargs={'queue_item_id': item.id}, task_id=item.task_id)

        item.refresh_from_db()
        self.assertEqual(item.status, 'failed')
        self.assertEqual(item.error_message, 'Tasca aturada manualment per un usuari.')

    def test_la_tasca_real_tanca_el_seu_item(self):
        item = self.enqueue('REGENERATE_PDFS')
        waiting = BillingQueue.objects.create(billing=self.billing, task_type='WINCEN_EXPORT', status='pending')

        billing_tasks.regenerate_billing_pdfs.apply(
            args=[self.billing.id], kwargs={'queue_item_id': item.id}, task_id=item.task_id)

        item.refresh_from_db()
        waiting.refresh_from_db()
        self.assertEqual(item.status, 'completed')
        self.assertEqual(waiting.status, 'running')

    # --- vista ------------------------------------------------------------

    def test_la_vista_retorna_503_si_no_pot_matar_la_tasca(self):
        item = self.enqueue()
        client = APIClient()
        client.force_authenticate(User.objects.create(username='queue-kill'))

        with mock.patch(REVOKE, side_effect=ConnectionError('redis no respon')):
            response = client.post(f'/billing/billing-queue/{item.id}/action/', {'action': 'kill'}, format='json')

        self.assertEqual(response.status_code, 503)
        self.assertIn('redis no respon', response.data['error'])
        item.refresh_from_db()
        self.assertEqual(item.status, 'running')

    def test_la_vista_mata_la_tasca(self):
        item = self.enqueue()
        client = APIClient()
        client.force_authenticate(User.objects.create(username='queue-kill'))

        with mock.patch(REVOKE) as revoke:
            response = client.post(f'/billing/billing-queue/{item.id}/action/', {'action': 'kill'}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'failed')
        revoke.assert_called_once_with(item.task_id, terminate=True, signal='SIGKILL')


class ReportQueueActionTests(TestCase):
    def setUp(self):
        self.report = AvailableReport.objects.create(name='Informe cua', function_name='bails_report')
        patcher = mock.patch.object(statistics_tasks.run_report_task, 'apply_async')
        self.apply_async = patcher.start()
        self.addCleanup(patcher.stop)

    def enqueue(self, payload=None):
        item = ReportQueue.objects.create(report=self.report, payload=payload or {}, status='pending')
        statistics_tasks.process_next_report_queue_item()
        item.refresh_from_db()
        return item

    def test_el_task_id_es_desa_abans_d_encuar_la_tasca(self):
        item = self.enqueue({'a': 1})
        self.assertEqual(item.status, 'running')
        kwargs = self.apply_async.call_args.kwargs
        self.assertEqual(kwargs['task_id'], item.task_id)
        self.assertEqual(kwargs['args'], ['bails_report', {'a': 1}])
        self.assertEqual(kwargs['kwargs'], {'queue_item_id': item.id})

    def test_kill_mata_la_tasca_i_engega_la_seguent(self):
        item = self.enqueue()
        waiting = ReportQueue.objects.create(report=self.report, payload={}, status='pending')
        with mock.patch(REVOKE) as revoke:
            statistics_tasks.apply_report_queue_action(item, 'kill')
        revoke.assert_called_once_with(item.task_id, terminate=True, signal='SIGKILL')
        item.refresh_from_db()
        waiting.refresh_from_db()
        self.assertEqual(item.status, 'failed')
        self.assertEqual(waiting.status, 'running')

    def test_si_el_revoke_falla_no_es_toca_res(self):
        item = self.enqueue()
        with mock.patch(REVOKE, side_effect=ConnectionError('redis no respon')):
            with self.assertRaises(QueueTaskRevokeError):
                statistics_tasks.apply_report_queue_action(item, 'skip')
        item.refresh_from_db()
        self.assertEqual(item.status, 'running')

    def test_l_informe_que_sobreviu_al_kill_no_trepitja_l_item(self):
        item = self.enqueue()
        with mock.patch(REVOKE):
            statistics_tasks.apply_report_queue_action(item, 'kill')
        waiting = ReportQueue.objects.create(report=self.report, payload={}, status='pending')

        with mock.patch.object(statistics_tasks, 'execute_report', return_value=(None, 'f.xlsx')):
            statistics_tasks.run_report_task.apply(
                args=['bails_report', {}], kwargs={'queue_item_id': item.id}, task_id=item.task_id)

        item.refresh_from_db()
        waiting.refresh_from_db()
        self.assertEqual(item.status, 'failed')
        self.assertEqual(waiting.status, 'pending')

    def test_l_informe_tanca_el_seu_item(self):
        item = self.enqueue()
        with mock.patch.object(statistics_tasks, 'execute_report', return_value=(None, 'f.xlsx')):
            statistics_tasks.run_report_task.apply(
                args=['bails_report', {}], kwargs={'queue_item_id': item.id}, task_id=item.task_id)
        item.refresh_from_db()
        self.assertEqual(item.status, 'completed')

    def test_l_informe_que_falla_marca_l_item_com_a_failed(self):
        item = self.enqueue()
        with mock.patch.object(statistics_tasks, 'execute_report', side_effect=ValueError('boom')):
            statistics_tasks.run_report_task.apply(
                args=['bails_report', {}], kwargs={'queue_item_id': item.id}, task_id=item.task_id)
        item.refresh_from_db()
        self.assertEqual(item.status, 'failed')
        self.assertEqual(item.error_message, 'boom')

    def test_la_vista_retorna_503_si_no_pot_matar_la_tasca(self):
        item = self.enqueue()
        client = APIClient()
        client.force_authenticate(User.objects.create(username='report-kill'))
        with mock.patch(REVOKE, side_effect=ConnectionError('redis no respon')):
            response = client.post(f'/statistics/report-queue/{item.id}/action/', {'action': 'kill'}, format='json')
        self.assertEqual(response.status_code, 503)
        item.refresh_from_db()
        self.assertEqual(item.status, 'running')
