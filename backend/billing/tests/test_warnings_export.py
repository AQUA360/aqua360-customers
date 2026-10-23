from datetime import date
from io import BytesIO
from types import SimpleNamespace
from unittest import mock

import openpyxl
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from billing.models import Billing, Invoice, InvoiceStatus, InvoiceWarning, Reading, ReadingAlert, ReadingBatch
from billing.tasks import export_batch_readings_task
from contract.models import Contract
from coredata.models import ConfigProject


FAKE_JOB = SimpleNamespace(task_id='task-1', id=1, name='export')


def _user_with_perm(username, codename):
    user = get_user_model().objects.create_user(username=username, password='x')
    user.user_permissions.add(Permission.objects.get(content_type__app_label='billing', codename=codename))
    return user


class TestBatchReadingsExport(TestCase):
    """L'exportació del detall del resum del lot conté les mateixes lectures que el llistat."""

    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('contract_terminated_status', 'TERMINATED'),
            ('communication_process_status_finalized_token', 'FINALIZED'),
            ('communication_status_sent_token', 'SENT'),
        ):
            ConfigProject.objects.get_or_create(token=token, defaults={'value': value})
        cls.user = _user_with_perm('export-readings', 'view_reading')
        cls.contract = Contract.objects.create(token='C-EXPORT-R')
        cls.batch = ReadingBatch.objects.create()
        cls.other_batch = ReadingBatch.objects.create()
        cls.alert_zero = ReadingAlert.objects.create(name='reading_alert_zero')

        def reading(value, days, alert=None, batch=None):
            return Reading.objects.create(
                contract=cls.contract, batch=batch or cls.batch, reading_date=date(2026, 5, 1),
                reading_value=value, consumption_days=days, alert=alert,
            )

        cls.correct_1 = reading(100, 30)
        cls.correct_2 = reading(110, 30)
        cls.warning = reading(0, 30, alert=cls.alert_zero)
        cls.out_of_range = reading(120, 90)
        reading(0, 30, alert=cls.alert_zero, batch=cls.other_batch)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def export(self, params):
        with mock.patch('billing.views.reading_view.enqueue_export', return_value=FAKE_JOB) as enqueue:
            response = self.client.post(f"{reverse('reading-export-by-batch-minimal')}?{params}")
        self.assertEqual(response.status_code, 202, response.content)
        self.assertEqual(response.data['export_job_id'], FAKE_JOB.id)
        return enqueue.call_args.kwargs['args'][0]

    def test_exporta_nomes_els_avisos_del_lot(self):
        self.assertEqual(self.export(f'batch={self.batch.id}&alert=any'), [self.warning.id])

    def test_exporta_un_avis_concret(self):
        self.assertEqual(self.export(f'batch={self.batch.id}&alert=reading_alert_zero'), [self.warning.id])

    def test_exporta_avis_de_rang_de_dates(self):
        # Mediana de 30 dies: la lectura de 90 dies queda fora del marge del 25%.
        self.assertEqual(self.export(f'batch={self.batch.id}&alert=warning_date_range'), [self.out_of_range.id])

    def test_conserva_l_ordenacio_del_llistat(self):
        ids = self.export(f'batch={self.batch.id}&alert=null&ordering=-reading_value')
        self.assertEqual(ids, [self.out_of_range.id, self.correct_2.id, self.correct_1.id])

    def test_mateixes_lectures_que_el_llistat(self):
        params = f'batch={self.batch.id}&alert=null'
        listed = self.client.get(f"{reverse('reading-list-by-batch-minimal')}?{params}")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(sorted(r['id'] for r in listed.data['results']), sorted(self.export(params)))

    def test_sense_lot_retorna_400(self):
        response = self.client.post(reverse('reading-export-by-batch-minimal'))
        self.assertEqual(response.status_code, 400)

    def test_sense_permis_de_veure_lectures_retorna_403(self):
        self.client.force_authenticate(get_user_model().objects.create_user(username='no-perm', password='x'))
        response = self.client.post(f"{reverse('reading-export-by-batch-minimal')}?batch={self.batch.id}")
        self.assertEqual(response.status_code, 403)

    def test_la_tasca_genera_l_excel_en_l_ordre_rebut(self):
        uploaded = {}

        def fake_upload(file, **kwargs):
            uploaded['bytes'] = file.read()
            return SimpleNamespace(id=7)

        with mock.patch('billing.tasks.upload_document', side_effect=fake_upload):
            result = export_batch_readings_task([self.warning.id, self.correct_1.id])

        self.assertEqual(result['status'], 'success', result)
        self.assertEqual(result['document_id'], 7)
        rows = list(openpyxl.load_workbook(BytesIO(uploaded['bytes'])).active.iter_rows(values_only=True))
        self.assertEqual(len(rows), 3)
        self.assertEqual([row[0] for row in rows[1:]], ['C-EXPORT-R', 'C-EXPORT-R'])
        # Columna d'avís traduïda (el nom de ReadingAlert és una clau de traducció).
        self.assertIn('Lectura 0', rows[1])
        self.assertEqual(rows[1][9], 0)
        self.assertEqual(rows[2][9], 100)


class TestBillingInvoicesExport(TestCase):
    """L'exportació del detall de pre-factures conté les mateixes factures que el llistat."""

    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('contract_terminated_status', 'TERMINATED'),
            ('invoice_status_cancelled_token', 'CANCELLED'),
            ('invoice_status_paid_token', 'PAID'),
            ('invoice_status_pending_token', 'PENDING'),
            ('payment_status_paid_token', 'PAID'),
            ('communication_process_status_cancelled_token', 'CANCELLED'),
        ):
            ConfigProject.objects.get_or_create(token=token, defaults={'value': value})
        InvoiceStatus.objects.get_or_create(token='PENDING', defaults={'name': 'Pendent'})
        cls.user = _user_with_perm('export-invoices', 'view_invoice')
        cls.contract = Contract.objects.create(token='C-EXPORT-F')
        cls.billing = Billing.objects.create()
        cls.other_billing = Billing.objects.create()
        cls.negative = InvoiceWarning.objects.create(name='Import negatiu')

        def invoice(serie, warning=None, excluded=False, billing=None):
            return Invoice.objects.create(
                contract=cls.contract, billing=billing or cls.billing, serie_final=serie,
                warning=warning, is_excluded=excluded, consumption_days=30,
            )

        cls.correct = invoice('PF/EXP/1')
        cls.warning = invoice('PF/EXP/2', warning=cls.negative)
        cls.excluded = invoice('PF/EXP/3', warning=cls.negative, excluded=True)
        invoice('PF/EXP/4', warning=cls.negative, billing=cls.other_billing)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def export(self, params=''):
        url = reverse('billing-invoices-export', args=[self.billing.id])
        with mock.patch('billing.views.billing_invoices_view.enqueue_export', return_value=FAKE_JOB) as enqueue:
            response = self.client.post(f'{url}?{params}')
        self.assertEqual(response.status_code, 202, response.content)
        return enqueue.call_args.kwargs['args'][0]

    def test_exporta_nomes_els_avisos_no_exclosos_de_la_facturacio(self):
        self.assertEqual(self.export('alert=any'), [self.warning.id])

    def test_exporta_un_avis_concret(self):
        self.assertEqual(self.export('alert=Import negatiu'), [self.warning.id])

    def test_exporta_les_excloses(self):
        self.assertEqual(self.export('is_excluded=true'), [self.excluded.id])

    def test_mateixes_factures_que_el_llistat(self):
        url = reverse('billing-invoices', args=[self.billing.id])
        listed = self.client.get(f'{url}?alert=null')
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([i['id'] for i in listed.data['results']], self.export('alert=null'))

    def test_sense_permis_de_veure_factures_retorna_403(self):
        self.client.force_authenticate(get_user_model().objects.create_user(username='no-perm-f', password='x'))
        response = self.client.post(reverse('billing-invoices-export', args=[self.billing.id]))
        self.assertEqual(response.status_code, 403)
