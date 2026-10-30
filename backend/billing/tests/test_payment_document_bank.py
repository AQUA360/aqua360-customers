import datetime
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from billing.utils.joined_payment_service import generate_report_joined_payment_pdf
from billing.utils.payment_pdf_service import generate_report_payment_pdf
from billing.views.generate_payment_doc_view import GeneratePaymentDocDownloadViewSet


class StopRender(Exception):
    pass


class PaymentDocumentBankTests(SimpleTestCase):
    def setUp(self):
        self.bank = MagicMock(iban='ES-SELECTED', swift='SELECTED', barcode_suffix='503', barcode_cif=None)
        self.default_bank = MagicMock(iban='ES-DEFAULT', swift='DEFAULT', barcode_suffix='501', barcode_cif=None)
        self.exploitation = MagicMock()
        self.exploitation.company.logo = None
        self.exploitation.company.vat = 'B12345678'
        self.exploitation.company.company_banks.filter.return_value.first.return_value = self.default_bank
        self.default_bank.configure_mock(id=1, is_default=True, is_active=True)
        self.exploitation.company.company_banks.all.return_value = [self.default_bank]
        self.payment = MagicMock()
        self.payment.token = '12345678901'
        self.payment.amount = 10
        self.payment.due_date = datetime.date(2026, 9, 1)
        self.payment.payment_bank = None
        self.payment.payment_type_token = 'DIRECT_DEBIT'
        self.payment.status = None
        self.payment.invoice = None
        self.payment.commitment_deposit = None

    def _payment_pdf_context(self):
        captured = {}
        def render(template, context):
            captured.update(context)
            raise StopRender()
        with patch('service.models.Exploitation') as model, \
             patch('billing.utils.payment_pdf_service.CompanySerializer') as serializer, \
             patch('billing.utils.payment_pdf_service.ConfigProject') as config, \
             patch('billing.utils.payment_pdf_service.generate_barcode', return_value=None) as generate, \
             patch('billing.utils.barcode_service.get_barcode_values', return_value={}), \
             patch('billing.utils.payment_pdf_service.exploitation_logo_source', return_value=None), \
             patch('service.serializers.company_bank_serializer.CompanyBankSerializer') as bank_serializer, \
             patch('billing.utils.payment_pdf_service.render_to_string', side_effect=render):
            model.objects.filter.return_value.first.return_value = self.exploitation
            config.objects.filter.return_value.values_list.return_value.first.return_value = 'BANK_PAYMENT'
            serializer.return_value.data = {'logo': None, 'vat': 'B12345678'}
            bank_serializer.return_value.data = {'iban': self.bank.iban}
            with self.assertRaisesMessage(Exception, 'Error generating report'):
                generate_report_payment_pdf(self.payment)
        return generate.call_args.args[0], captured

    def test_invoice_commitment_and_transfer_use_selected_bank_for_barcode_and_template(self):
        invoice = MagicMock(exploitation=self.exploitation, payment_company_bank=self.bank)
        invoice.contract = None
        invoice.contract_request = None
        commitment = MagicMock()
        commitment.invoices.exists.return_value = True
        commitment.invoices.first.return_value = invoice
        for scenario in ('invoice', 'commitment', 'commitment_contract', 'transfer', 'bank_payment'):
            with self.subTest(scenario=scenario):
                selected = scenario in ('transfer', 'bank_payment')
                invoice.payment_company_bank = self.default_bank if selected else self.bank
                commitment.invoices.first.return_value = (SimpleNamespace(payment_company_bank=None, exploitation=self.exploitation)
                                                          if scenario == 'commitment_contract' else invoice)
                commitment.contract.payment.company_iban = self.bank
                self.payment.invoice = invoice if not scenario.startswith('commitment') else None
                self.payment.commitment_deposit = commitment if scenario.startswith('commitment') else None
                self.payment.payment_type_token = {'transfer': 'BANK_TRANSFER', 'bank_payment': 'BANK_PAYMENT'}.get(scenario, 'DIRECT_DEBIT')
                self.payment.payment_bank = self.bank.iban if selected else None
                self.exploitation.company.company_banks.filter.return_value.first.return_value = self.bank if selected else self.default_bank
                data, context = self._payment_pdf_context()
                self.assertIs(data['company_bank'], self.bank)
                self.assertEqual(context['company_iban'], self.bank.iban)
                self.assertEqual(context['company_swift'], self.bank.swift)

    def test_download_view_uses_invoice_bank_for_barcode_and_template(self):
        invoice = MagicMock(exploitation=self.exploitation, payment_company_bank=self.bank)
        self.payment.invoice = invoice
        self.payment.commitment_deposit = None
        captured = {}
        def render(template, context):
            captured.update(context)
            raise StopRender()
        request = MagicMock()
        request.GET.get.return_value = None
        with patch('billing.views.generate_payment_doc_view.Payment') as model, \
             patch('billing.views.generate_payment_doc_view.CompanySerializer') as serializer, \
             patch('billing.views.generate_payment_doc_view.ConfigProject'), \
             patch('billing.views.generate_payment_doc_view.exploitation_logo_source', return_value=None), \
             patch('billing.utils.barcode_service.get_barcode_values', return_value={}) as values, \
             patch('billing.utils.barcode_service.generate_barcode', return_value=BytesIO(b'barcode')), \
             patch('billing.views.generate_payment_doc_view.render_to_string', side_effect=render):
            model.objects.get.return_value = self.payment
            serializer.return_value.data = {'logo': None, 'vat': 'B12345678'}
            with self.assertRaises(StopRender):
                GeneratePaymentDocDownloadViewSet().get(request, 1)
        self.assertIs(values.call_args.args[0]['company_bank'], self.bank)
        self.assertEqual(captured['company_iban'], self.bank.iban)
        self.assertEqual(captured['company_swift'], self.bank.swift)

    def test_grouped_document_uses_common_bank_for_barcode_and_template(self):
        invoice = SimpleNamespace(payment_company_bank=self.bank)
        payments = MagicMock()
        payments.__iter__.return_value = iter([SimpleNamespace(invoice=invoice)])
        joined = MagicMock()
        joined.contract.supply_point_default.connection.exploitation = self.exploitation
        joined.payments.all.return_value.order_by.return_value = payments
        joined.due_date = datetime.date(2026, 9, 1)
        joined.token = '12345678901'
        joined.total_final = 10
        captured = {}
        def render(template, context):
            captured.update(context)
            raise StopRender()
        with patch('billing.utils.joined_payment_service.CompanySerializer') as serializer, \
             patch('billing.utils.joined_payment_service.ConfigProject'), \
             patch('billing.utils.joined_payment_service.generate_barcode', return_value=None) as generate, \
             patch('billing.utils.barcode_service.get_barcode_values', return_value={}), \
             patch('billing.utils.joined_payment_service.exploitation_logo_source', return_value=None), \
             patch('billing.utils.joined_payment_service._payments_for_template', return_value=[]), \
             patch('billing.utils.joined_payment_service.render_to_string', side_effect=render):
            serializer.return_value.data = {'logo': None, 'vat': 'B12345678'}
            with self.assertRaisesMessage(Exception, 'Error generating report'):
                generate_report_joined_payment_pdf(joined, None)
        self.assertIs(generate.call_args.args[0]['company_bank'], self.bank)
        self.assertEqual(captured['company_iban'], self.bank.iban)
        self.assertEqual(captured['company_swift'], self.bank.swift)

    def test_grouped_document_with_mixed_banks_uses_default_bank(self):
        payments = MagicMock()
        payments.__iter__.return_value = iter([
            SimpleNamespace(invoice=SimpleNamespace(payment_company_bank=self.bank)),
            SimpleNamespace(invoice=SimpleNamespace(payment_company_bank=self.default_bank)),
        ])
        joined = MagicMock()
        joined.contract.supply_point_default.connection.exploitation = self.exploitation
        joined.payments.all.return_value.order_by.return_value = payments
        with patch('billing.utils.joined_payment_service.generate_barcode') as generate:
            generate.side_effect = StopRender()
            with self.assertRaisesMessage(Exception, 'Error generating report'):
                generate_report_joined_payment_pdf(joined, None)
        self.assertIs(generate.call_args.args[0]['company_bank'], self.default_bank)

    def test_claim_document_uses_common_bank_for_barcode_and_template(self):
        from claimrequest.tasks import generate_claim_document_pdf

        contract = MagicMock()
        contract.language = 'ca'
        contract.supply_point_default.connection.exploitation = self.exploitation
        contract.supply_point_default.address = None
        contract.supply_point_default.meter = None
        claim = MagicMock()
        claim.current_step.step_template.group_payments = True
        step = MagicMock()
        step.duration = 3
        step.document_type.token = 'CLAIM'
        joined = MagicMock()
        joined.status.token = 'ACTIVE'
        joined.token = '12345678901'
        joined.due_date = datetime.date(2026, 9, 1)
        joined.total_final = 10
        original, expenses = MagicMock(), MagicMock()
        original.aggregate.return_value = {'total': 10}
        expenses.aggregate.return_value = {'total': 0}
        joined.payments.filter.side_effect = [MagicMock(distinct=lambda: original), MagicMock(distinct=lambda: expenses)]
        invoices = MagicMock()
        invoices.__iter__.return_value = iter([])
        invoices.count.return_value = 0
        captured = {}
        def render(template, context):
            captured.update(context)
            raise StopRender()
        with patch('claimrequest.tasks.ClaimRequest') as claim_model, \
             patch('claimrequest.tasks.Contract') as contract_model, \
             patch('claimrequest.tasks.ClaimRequestStep') as step_model, \
             patch('claimrequest.tasks.JoinedPayment') as joined_model, \
             patch('claimrequest.tasks.Invoice') as invoice_model, \
             patch('claimrequest.tasks.ClaimRequestPayment'), \
             patch('claimrequest.tasks.ConfigProject') as config, \
             patch('claimrequest.tasks.CompanySerializer') as company_serializer, \
             patch('claimrequest.tasks.PersonSerializer') as person_serializer, \
             patch('claimrequest.tasks.contract_company_logo', return_value='logo'), \
             patch('claimrequest.tasks.build_logo_path', return_value=None), \
             patch('claimrequest.tasks.get_contract_company', return_value=None), \
             patch('claimrequest.tasks.exploitation_logo_source', return_value=None), \
             patch('claimrequest.tasks.get_payments_company_bank', return_value=self.bank) as resolve, \
             patch('claimrequest.tasks.generate_barcode', return_value=None) as generate, \
             patch('claimrequest.tasks.get_barcode_values', return_value={}), \
             patch('claimrequest.tasks.render_to_string', side_effect=render):
            claim_model.objects.get.return_value = claim
            contract_model.objects.get.return_value = contract
            step_model.objects.get.return_value = step
            joined_model.objects.get.return_value = joined
            invoice_model.objects.filter.return_value.distinct.return_value = invoices
            invoices.filter.return_value = invoices
            invoices.distinct.return_value = invoices
            config.objects.get.return_value.value = 'CANCELLED'
            config.objects.filter.return_value.first.return_value = None
            company_serializer.return_value.data = {'logo': None, 'vat': 'B12345678'}
            person_serializer.return_value.data = {'addresses': [], 'debt_amount': 0}
            with self.assertRaisesMessage(Exception, 'Error generating claim document') as error:
                generate_claim_document_pdf(1, 2, 3, 4)
            self.assertEqual(str(error.exception), 'Error generating claim document: ')
        resolve.assert_called_once_with(original, self.exploitation.company)
        self.assertIs(generate.call_args.args[0]['company_bank'], self.bank)
        self.assertIs(captured['company_bank'], self.bank)
