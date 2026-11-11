import json
from datetime import date

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from billing.models import Invoice, InvoiceStatus
from billing.tests.test_return_after_payment_method_change import ReturnAfterPaymentMethodChangeBase
from billing.utils.payment_return_warnings import annotate_rejection_warnings, is_rectified_invoice
from billing.utils.sepa_service import getDocumentSEPAPayments
from contract.models import ContractStatus
from coredata.models import ConfigProject


class ReturnWarningsBase(ReturnAfterPaymentMethodChangeBase):
    """Pagament per domiciliació retornat d'un abonat de baixa o d'una factura anul·lada i refeta."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        ConfigProject.objects.update_or_create(token='contract_terminated_status', defaults={'value': 'TERMINATED'})
        ConfigProject.objects.update_or_create(token='invoice_status_cancelled_token', defaults={'value': 'CANCELLED'})
        cls.terminated_status = ContractStatus.objects.create(token='TERMINATED', name='Baixa')
        cls.active_status = ContractStatus.objects.create(token='ACTIVE', name='Actiu')
        cls.invoice_status['CANCELLED'] = InvoiceStatus.objects.create(token='CANCELLED', name='Anul·lada')

    def setUp(self):
        super().setUp()
        self.contract.status = self.active_status
        self.contract.save()

    def terminate_contract(self):
        self.contract.status = self.terminated_status
        self.contract.termination_date = date(2026, 9, 15)
        self.contract.save()

    def rectify_and_refactor_invoice(self):
        """Anul·lació com la de la supressió: factura anul·lada, pagament abonat, rectificativa i factura refeta."""
        rectifying = Invoice.objects.create(token='F-RET-R', contract=self.contract, serie_final='FR/RET')
        Invoice.objects.create(token='F-RET-2', contract=self.contract, serie_final='FC/RET2', refactored_token=self.invoice.token)
        Invoice.objects.filter(id=self.invoice.id).update(status=self.invoice_status['CANCELLED'], return_token=rectifying.token)
        self.payment.status = self.payment_status['-6']
        self.payment.save()
        self.invoice.refresh_from_db()

    def warnings(self):
        return annotate_rejection_warnings([{'payment_id': self.payment.id}])[0]


class TestReturnWarnings(ReturnWarningsBase):

    def test_active_contract_and_paid_invoice_have_no_warnings(self):
        warnings = self.warnings()

        self.assertFalse(warnings['contract_terminated'])
        self.assertIsNone(warnings['contract_termination_date'])
        self.assertFalse(warnings['invoice_rectified'])

    def test_terminated_contract_is_flagged(self):
        self.terminate_contract()

        warnings = self.warnings()

        self.assertTrue(warnings['contract_terminated'])
        self.assertEqual(warnings['contract_termination_date'], '2026-09-15')

    def test_rectified_and_refactored_invoice_is_flagged(self):
        self.rectify_and_refactor_invoice()

        warnings = self.warnings()

        self.assertTrue(warnings['invoice_rectified'])
        self.assertEqual(warnings['rectifying_invoice'], 'FR/RET')
        self.assertEqual(warnings['refactored_invoice'], 'FC/RET2')

    def test_cancelled_invoice_without_rectifying_token_is_rectified(self):
        Invoice.objects.filter(id=self.invoice.id).update(status=self.invoice_status['CANCELLED'])
        self.invoice.refresh_from_db()

        self.assertTrue(is_rectified_invoice(self.invoice))

    def test_rows_without_payment_are_left_untouched(self):
        rows = annotate_rejection_warnings([{'not_found': True}])

        self.assertEqual(rows, [{'not_found': True}])

    def test_sepa_preview_includes_the_warnings(self):
        self.terminate_contract()
        self.rectify_and_refactor_invoice()
        client_data = {'document_end_id': self.payment.token, 'reject_token': 'AM04', 'name': 'TITULAR'}

        rejections = getDocumentSEPAPayments('NO-REMESA', {'name': 'EMPRESA'}, [client_data], '', None, '2026-09-09')

        self.assertEqual(len(rejections), 1)
        self.assertTrue(rejections[0]['contract_terminated'])
        self.assertTrue(rejections[0]['invoice_rectified'])
        self.assertEqual(rejections[0]['refactored_invoice'], 'FC/RET2')


class TestManageRejectionWithWarnings(ReturnWarningsBase):

    def post_return(self, claim=False):
        client = APIClient()
        client.force_authenticate(self.user)
        rejection = {'id': self.payment.id, 'skip_return': False, 'rjt_dt': '2026-09-09',
                     'motive_id': self.motive.id, 'motive': self.motive.name}
        data = {
            'payments_to_return': json.dumps([rejection]),
            'return_payments': json.dumps([]),
            'claim_payments': json.dumps([self.payment.id] if claim else []),
            'return_date': '2026-09-09',
        }
        return client.post(reverse('payment-manage-rejection-payments'), data, format='multipart')

    def test_rectified_invoice_is_not_reopened_nor_claimed(self):
        self.rectify_and_refactor_invoice()

        response = self.post_return(claim=True)

        self.assertEqual(response.status_code, 200)
        self.payment.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(self.payment.status.token, '-6')
        self.assertEqual(self.invoice.status.token, 'CANCELLED')
        self.assertFalse(self.payment.movements.filter(current_status__token='-2').exists())
        self.assertFalse(self.payment.claim_requests.exists())
        # El motiu del retorn sí que queda informat
        self.assertEqual(self.payment.reject, self.motive)

    def test_terminated_contract_is_returned_as_usual(self):
        self.terminate_contract()

        response = self.post_return()

        self.assertEqual(response.status_code, 200)
        self.payment.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(self.payment.status.token, '-2')
        self.assertEqual(self.invoice.status.token, 'EXPIRED')
