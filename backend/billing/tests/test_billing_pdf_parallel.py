from types import SimpleNamespace
from unittest import mock

from django.test import TestCase

from billing import tasks as billing_tasks
from billing.models import Billing, BillingQueue, BillingStatus
from coredata.models import ConfigProject

REVOKE = 'customers.celery.app.control.revoke'
GENERATE_PDF = 'billing.tasks._generate_invoice_pdf'


def fake_task(task_id='T', called_directly=False, concurrency=8):
    return SimpleNamespace(
        request=SimpleNamespace(id=task_id, called_directly=called_directly, is_eager=False),
        app=SimpleNamespace(conf=SimpleNamespace(worker_concurrency=concurrency)),
    )


class FinishedResult:
    """AsyncResult d'una subtasca ja acabada."""
    results = {}

    def __init__(self, task_id):
        self.state = 'SUCCESS'
        self.result = self.results.get(task_id, {'generated': 0})
        self.info = self.result

    def ready(self):
        return True

    def successful(self):
        return True


class BillingPdfParallelTests(TestCase):
    """PDF de la facturació repartits en subtasques; la confirmació continua en sèrie."""

    def setUp(self):
        self.progress = []

    def on_progress(self, done, generated):
        self.progress.append((done, generated))

    def test_cridada_directament_es_fa_en_serie_i_no_compta_els_que_fallen(self):
        with mock.patch(GENERATE_PDF, side_effect=lambda invoice_id, config_cache=None: invoice_id != 2) as generate, \
                mock.patch.object(billing_tasks.generate_billing_pdfs_chunk, 'apply_async') as apply_async:
            generated, completed = billing_tasks.generate_billing_pdfs(
                fake_task(called_directly=True), [1, 2, 3], {}, None, self.on_progress,
            )
        apply_async.assert_not_called()
        self.assertEqual(generate.call_count, 3)
        self.assertEqual((generated, completed), (2, True))
        # El progrés compta el que ha fallat; els generats, no
        self.assertEqual(self.progress[-1], (3, 2))

    def test_pocs_processos_al_worker_es_fa_en_serie(self):
        with mock.patch(GENERATE_PDF, return_value=True), \
                mock.patch.object(billing_tasks.generate_billing_pdfs_chunk, 'apply_async') as apply_async:
            billing_tasks.generate_billing_pdfs(fake_task(concurrency=1), list(range(200)), {}, None, self.on_progress)
        apply_async.assert_not_called()

    def test_les_subtasques_caben_als_processos_del_worker(self):
        workers = billing_tasks._billing_pdf_workers
        with mock.patch.object(billing_tasks, 'billing_pdf_parallel_setting', return_value=6):
            # CELERY_WORKER_CONCURRENCY: la principal ocupa un procés
            self.assertEqual(workers(fake_task(concurrency=4), 1000), 3)
            self.assertEqual(workers(fake_task(concurrency=16), 1000), 6)
            # Sense configurar, tants processos com CPU (com fa Celery)
            with mock.patch('billing.tasks.os.cpu_count', return_value=3):
                self.assertEqual(workers(fake_task(concurrency=None), 1000), 2)
            # Poques factures: com a mínim 20 per subtasca
            self.assertEqual(workers(fake_task(concurrency=16), 50), 2)

    def test_el_nombre_de_subtasques_surt_del_config_project(self):
        setting = billing_tasks.billing_pdf_parallel_setting
        ConfigProject.objects.filter(token=billing_tasks.BILLING_PDF_PARALLEL_WORKERS_TOKEN).delete()
        self.assertEqual(setting(), billing_tasks.BILLING_PDF_PARALLEL_WORKERS_DEFAULT)
        config = ConfigProject.objects.create(token=billing_tasks.BILLING_PDF_PARALLEL_WORKERS_TOKEN, value='2')
        self.assertEqual(setting(), 2)
        for value, expected in (('1', 1), ('0', 1), ('100', billing_tasks.BILLING_PDF_MAX_SUBTASKS),
                                ('', billing_tasks.BILLING_PDF_PARALLEL_WORKERS_DEFAULT),
                                ('quatre', billing_tasks.BILLING_PDF_PARALLEL_WORKERS_DEFAULT)):
            ConfigProject.objects.filter(id=config.id).update(value=value)
            self.assertEqual(setting(), expected, value)

    def test_reparteix_les_factures_en_subtasques_amb_ids_fixos(self):
        invoice_ids = list(range(1, 101))
        FinishedResult.results = {f'T-pdf-{index}': {'generated': 25 - index} for index in range(4)}
        with mock.patch.object(billing_tasks, 'billing_pdf_parallel_setting', return_value=4), \
                mock.patch.object(billing_tasks.generate_billing_pdfs_chunk, 'apply_async') as apply_async, \
                mock.patch('celery.result.AsyncResult', FinishedResult), \
                mock.patch(GENERATE_PDF) as generate:
            generated, completed = billing_tasks.generate_billing_pdfs(fake_task(), invoice_ids, {'a': 'b'}, None, self.on_progress)

        generate.assert_not_called()
        task_ids = [call.kwargs['task_id'] for call in apply_async.call_args_list]
        self.assertEqual(task_ids, billing_tasks.billing_pdf_subtask_ids('T')[:4])
        chunks = [call.kwargs['args'][0] for call in apply_async.call_args_list]
        self.assertEqual(sorted(sum(chunks, [])), invoice_ids)
        self.assertEqual({len(chunk) for chunk in chunks}, {25})
        self.assertEqual((generated, completed), (25 + 24 + 23 + 22, True))
        self.assertEqual(self.progress[-1], (100, None))

    def test_si_no_es_pot_encuar_una_subtasca_la_fa_la_principal(self):
        FinishedResult.results = {}
        with mock.patch.object(billing_tasks, 'billing_pdf_parallel_setting', return_value=2), \
                mock.patch.object(billing_tasks.generate_billing_pdfs_chunk, 'apply_async',
                                  side_effect=[None, Exception('broker caigut')]), \
                mock.patch('celery.result.AsyncResult', FinishedResult), \
                mock.patch(GENERATE_PDF, return_value=True) as generate:
            generated, completed = billing_tasks.generate_billing_pdfs(fake_task(), list(range(40)), {}, None, self.on_progress)
        self.assertEqual(generate.call_count, 20)
        self.assertEqual((generated, completed), (20, True))


class FailedResult(FinishedResult):
    """AsyncResult d'una subtasca que ha petat."""
    failed = set()

    def __init__(self, task_id):
        super().__init__(task_id)
        if task_id in self.failed:
            self.state, self.result = 'FAILURE', RuntimeError('ha petat')

    def successful(self):
        return self.state == 'SUCCESS'


class BillingPdfChunkTests(TestCase):
    def setUp(self):
        statuses = {}
        for token, default in (('billing_batch_processing_documents', 'Q-DOCS'), ('billing_batch_pending', 'Q-PENDING')):
            value = ConfigProject.objects.get_or_create(token=token, defaults={'value': default})[0].value
            statuses[token] = BillingStatus.objects.get_or_create(token=value, defaults={'name': value})[0]
        status = statuses['billing_batch_processing_documents']
        self.billing = Billing.objects.create(name='Billing PDF', status=status)
        self.item = BillingQueue.objects.create(
            billing=self.billing, task_type='DEFINITIVE_INVOICE', status='running', task_id='T',
        )

    def run_chunk(self, invoice_ids, parent_task_id='T'):
        return billing_tasks.generate_billing_pdfs_chunk.apply(
            args=[invoice_ids, {}], kwargs={'queue_item_id': self.item.id, 'parent_task_id': parent_task_id},
        ).result

    def test_compta_a_la_cua_nomes_els_generats(self):
        with mock.patch(GENERATE_PDF, side_effect=lambda invoice_id, config_cache=None: invoice_id != 2):
            result = self.run_chunk([1, 2, 3])
        self.item.refresh_from_db()
        self.assertEqual(result, {'generated': 2, 'stopped': False})
        self.assertEqual(self.item.documents_generated, 2)

    def test_no_fa_res_si_la_tasca_principal_ja_no_es_la_de_l_item(self):
        with mock.patch(GENERATE_PDF) as generate:
            result = self.run_chunk([1, 2, 3], parent_task_id='VELLA')
        generate.assert_not_called()
        self.assertTrue(result['stopped'])

    def test_la_principal_deixa_d_esperar_si_l_han_aturat(self):
        class Running:
            state, info = 'STARTED', None

            def __init__(self, task_id):
                pass

            def ready(self):
                return False

        BillingQueue.objects.filter(id=self.item.id).update(status='failed')
        with mock.patch.object(billing_tasks, 'billing_pdf_parallel_setting', return_value=2), \
                mock.patch.object(billing_tasks.generate_billing_pdfs_chunk, 'apply_async'), \
                mock.patch('celery.result.AsyncResult', Running), \
                mock.patch('billing.tasks.time.sleep') as sleep:
            generated, completed = billing_tasks.generate_billing_pdfs(
                fake_task(), list(range(40)), {}, self.item.id, lambda done, generated: None,
            )
        self.assertFalse(completed)
        sleep.assert_not_called()

    def test_en_serie_tambe_compta_a_la_cua(self):
        with mock.patch(GENERATE_PDF, side_effect=lambda invoice_id, config_cache=None: invoice_id != 2):
            generated, completed = billing_tasks.generate_billing_pdfs(
                fake_task(called_directly=True), [1, 2, 3], {}, self.item.id, lambda done, generated: None,
            )
        self.item.refresh_from_db()
        self.assertEqual((generated, completed, self.item.documents_generated), (2, True, 2))

    def test_un_tros_fallit_el_refa_la_principal_nomes_amb_les_que_falten(self):
        FinishedResult.results = {}
        FailedResult.failed = {'T-pdf-1'}
        chunks = {}
        with mock.patch.object(billing_tasks, 'billing_pdf_parallel_setting', return_value=2), \
                mock.patch.object(billing_tasks.generate_billing_pdfs_chunk, 'apply_async',
                                  side_effect=lambda args, **kw: chunks.update({kw['task_id']: args[0]})), \
                mock.patch('celery.result.AsyncResult', FailedResult), \
                mock.patch.object(billing_tasks, '_invoices_without_new_pdf',
                                  side_effect=lambda ids, last: ids[:3]) as missing, \
                mock.patch(GENERATE_PDF, return_value=True) as generate:
            generated, completed = billing_tasks.generate_billing_pdfs(
                fake_task(), list(range(40)), {}, self.item.id, lambda done, generated: None,
            )
        self.assertTrue(completed)
        missing.assert_called_once()
        self.assertEqual(missing.call_args.args[0], chunks['T-pdf-1'])
        self.assertEqual([call.args[0] for call in generate.call_args_list], chunks['T-pdf-1'][:3])
        self.item.refresh_from_db()
        self.assertEqual((generated, self.item.documents_generated), (3, 3))

    def test_factures_sense_pdf_nou(self):
        from billing.models import Invoice
        from documentmanager.models import Document
        old = Document.objects.create(entity_id=0, service='hdd')
        # bulk_create: sense el save() de la factura, que demana configuració
        done, pending, never = Invoice.objects.bulk_create([Invoice() for _ in range(3)])
        Invoice.objects.filter(id=pending.id).update(invoice_file=old)
        Invoice.objects.filter(id=done.id).update(invoice_file=Document.objects.create(entity_id=0, service='hdd'))
        self.assertEqual(
            billing_tasks._invoices_without_new_pdf([done.id, pending.id, never.id], old.id),
            [pending.id, never.id],
        )

    def test_si_l_han_aturat_no_es_dona_per_acabada_encara_que_les_subtasques_hagin_plegat(self):
        FinishedResult.results = {f'T-pdf-{index}': {'generated': 0, 'stopped': True} for index in range(2)}
        BillingQueue.objects.filter(id=self.item.id).update(status='failed')
        with mock.patch.object(billing_tasks, 'billing_pdf_parallel_setting', return_value=2), \
                mock.patch.object(billing_tasks.generate_billing_pdfs_chunk, 'apply_async'), \
                mock.patch('celery.result.AsyncResult', FinishedResult):
            generated, completed = billing_tasks.generate_billing_pdfs(
                fake_task(), list(range(40)), {}, self.item.id, lambda done, generated: None,
            )
        self.assertFalse(completed)

    def test_kill_revoca_tambe_les_subtasques_de_pdf(self):
        with mock.patch(REVOKE) as revoke, mock.patch('billing.tasks.process_next_queue_item'):
            billing_tasks.apply_billing_queue_action(self.item, 'kill')
        revoke.assert_called_once_with(
            ['T', *billing_tasks.billing_pdf_subtask_ids('T')], terminate=True, signal='SIGKILL',
        )


class ChartHistoryInPdfLoopTests(TestCase):
    """Els PDF es generen amb l'historial del gràfic precarregat per trossos, només si algun missatge té gràfic."""

    def seen_scopes(self, invoice_ids):
        from billing.utils import charts_service
        seen = []
        for invoice_id in billing_tasks._with_chart_history(invoice_ids):
            history = charts_service._chart_history.get()
            seen.append((invoice_id, history.has(SimpleNamespace(id=invoice_id)) if history else None))
        return seen

    def test_sense_missatges_de_grafic_no_es_precarrega(self):
        self.assertEqual(self.seen_scopes([1, 2]), [(1, None), (2, None)])

    def test_amb_grafic_es_precarrega_per_trossos(self):
        from billing.models import Message
        Message.objects.create(message_type='GRAPHIC')
        with mock.patch.object(billing_tasks, 'CHART_HISTORY_BATCH_SIZE', 2), \
                mock.patch('billing.utils.charts_service.ChartHistory') as history_class:
            history_class.side_effect = lambda invoices: SimpleNamespace(has=lambda invoice: True)
            seen = self.seen_scopes([1, 2, 3])
        self.assertEqual([invoice_id for invoice_id, _ in seen], [1, 2, 3])
        self.assertTrue(all(has for _, has in seen))
        self.assertEqual(history_class.call_count, 2)
