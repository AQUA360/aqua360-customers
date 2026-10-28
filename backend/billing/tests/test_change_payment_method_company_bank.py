from decimal import Decimal

from django.urls import reverse
from rest_framework.test import APIClient

from billing.models import Payment
from billing.tests.test_return_after_payment_method_change import ReturnAfterPaymentMethodChangeBase
from contract.models import PaymentType
from service.models import Company, CompanyBank


class TestChangePaymentMethodCompanyBank(ReturnAfterPaymentMethodChangeBase):
    """Canvi a transferència d'una factura pendent triant el compte de l'empresa on s'ha de pagar."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.bank_transfer = PaymentType.objects.create(token='BANK_TRANSFER', name='Transferència')
        cls.company = Company.objects.create(name='Empresa A')
        cls.other_company = Company.objects.create(name='Empresa B')
        cls.bank_1 = CompanyBank.objects.create(company=cls.company, iban='ES1100000000000000000001', swift='AAAAESBB')
        cls.bank_2 = CompanyBank.objects.create(company=cls.company, iban='ES2200000000000000000002', swift='CCCCESDD')
        cls.other_bank = CompanyBank.objects.create(company=cls.other_company, iban='ES3300000000000000000003', swift='EEEEESFF')
        cls.inactive_bank = CompanyBank.objects.create(
            company=cls.company, iban='ES4400000000000000000004', swift='GGGGESHH', is_active=False)

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.invoice.status = self.invoice_status['CONFIRMED']
        self.invoice.company = self.company
        self.invoice.payment_company_bank = self.bank_1
        self.invoice.save()
        self.pending = Payment.objects.create(
            token='P-RET-2', amount=Decimal('10.00'), invoice=self.invoice,
            status=self.payment_status['1'], payment_type_token='DIRECT_DEBIT')

    def change_method(self, payment_type, company_bank=None, payment_bank=None, payment_swift=None):
        return self.client.put(
            reverse('invoice-change-payment-method-invoice', args=[self.invoice.id]),
            {'payment_type_final': payment_type.id, 'payment_bank_final': payment_bank,
             'payment_swift_final': payment_swift,
             'payment_company_bank': company_bank.id if company_bank else None}, format='json')

    def test_bank_transfer_saves_selected_company_bank(self):
        response = self.change_method(self.bank_transfer, self.bank_2)

        self.assertEqual(response.status_code, 200)
        self.invoice.refresh_from_db()
        self.pending.refresh_from_db()
        self.assertEqual(self.invoice.payment_company_bank, self.bank_2)
        self.assertEqual(self.invoice.payment_bank_final, self.bank_2.iban)
        self.assertEqual(self.invoice.payment_swift_final, self.bank_2.swift)
        self.assertEqual(self.pending.payment_type_token, 'BANK_TRANSFER')
        self.assertEqual(self.pending.payment_bank, self.bank_2.iban)
        self.assertEqual(self.pending.payment_swift, self.bank_2.swift)

    def test_bank_of_another_company_is_rejected(self):
        response = self.change_method(self.bank_transfer, self.other_bank)

        self.assertEqual(response.status_code, 400)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.payment_company_bank, self.bank_1)
        self.assertEqual(self.invoice.payment_type_token_final, 'DIRECT_DEBIT')

    def test_inactive_bank_is_rejected(self):
        response = self.change_method(self.bank_transfer, self.inactive_bank)

        self.assertEqual(response.status_code, 400)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.payment_type_token_final, 'DIRECT_DEBIT')

    def test_bank_transfer_requires_a_company_bank(self):
        response = self.change_method(self.bank_transfer, payment_bank='ES5500000000000000000005', payment_swift='IIIIESJJ')

        self.assertEqual(response.status_code, 400)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.payment_type_token_final, 'DIRECT_DEBIT')

    def test_bank_transfer_ignores_request_iban_when_company_has_no_banks(self):
        self.invoice.company = Company.objects.create(name='Empresa sense comptes')
        self.invoice.save()

        response = self.change_method(self.bank_transfer, payment_bank='ES5500000000000000000005', payment_swift='IIIIESJJ')

        self.assertEqual(response.status_code, 200)
        self.invoice.refresh_from_db()
        self.pending.refresh_from_db()
        self.assertEqual(self.invoice.payment_type_token_final, 'BANK_TRANSFER')
        self.assertIsNone(self.invoice.payment_bank_final)
        self.assertIsNone(self.invoice.payment_swift_final)
        self.assertIsNone(self.pending.payment_bank)
        self.assertIsNone(self.pending.payment_swift)

    def test_bank_is_rejected_when_invoice_has_no_company(self):
        self.invoice.company = None
        self.invoice.save()

        response = self.change_method(self.bank_transfer, self.bank_2)

        self.assertEqual(response.status_code, 400)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.payment_type_token_final, 'DIRECT_DEBIT')

    def test_company_bank_is_ignored_when_not_bank_transfer(self):
        self.change_method(self.bank_transfer, self.bank_2)

        response = self.change_method(self.cash, self.bank_2)

        self.assertEqual(response.status_code, 200)
        self.invoice.refresh_from_db()
        self.pending.refresh_from_db()
        # El compte de cobrament es manté (document de cobrament, comptabilitat), però no el SWIFT
        self.assertEqual(self.invoice.payment_company_bank, self.bank_2)
        self.assertIsNone(self.invoice.payment_bank_final)
        self.assertIsNone(self.invoice.payment_swift_final)
        self.assertIsNone(self.pending.payment_swift)
        self.assertEqual(self.invoice.payment_type_token_final, 'CASH')

    def test_direct_debit_after_transfer_keeps_iban_and_swift_together(self):
        self.change_method(self.bank_transfer, self.bank_2)

        response = self.change_method(
            self.direct_debit, payment_bank='ES5500000000000000000005', payment_swift='IIIIESJJ')

        self.assertEqual(response.status_code, 200)
        self.invoice.refresh_from_db()
        self.pending.refresh_from_db()
        self.assertEqual(self.invoice.payment_bank_final, 'ES5500000000000000000005')
        self.assertEqual(self.invoice.payment_swift_final, 'IIIIESJJ')
        self.assertEqual(self.pending.payment_bank, 'ES5500000000000000000005')
        self.assertEqual(self.pending.payment_swift, 'IIIIESJJ')
