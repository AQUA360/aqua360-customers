from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from billing.models import Payment, PaymentRemittance, PaymentRemittanceStatus
from billing.utils.remittance_bank_check import (
    ISSUE_BIC, ISSUE_COMPANY_VAT, ISSUE_CREDITOR_ID, ISSUE_IBAN, ISSUE_INVALID_BIC,
    ISSUE_INVALID_IBAN, ISSUE_NO_COMPANY, RemittanceBankDataError, check_company_banks,
    get_company_bank_issues,
)
from coredata.models import Bank, ConfigProject
from service.models import Company, CompanyBank

VALID_IBAN = 'ES9121000418450200051332'


class TestCompanyBankIssues(TestCase):
    """Les dades del compte de l'empresa que necessita el fitxer SEPA."""

    def setUp(self):
        self.company = Company.objects.create(name='Empresa', alias='Empresa', vat='B00000000')
        self.entity = Bank.objects.create(token='2100', name='Entitat')

    def bank(self, **kwargs):
        data = {
            'company': self.company, 'bank': self.entity, 'iban': VALID_IBAN,
            'swift': 'CAIXESBBXXX', 'sepa_cred_identifier': 'ES00000B00000000', 'is_active': True,
        }
        data.update(kwargs)
        return CompanyBank.objects.create(**data)

    def test_compte_complet(self):
        self.assertEqual(get_company_bank_issues(self.bank()), [])

    def test_iban_i_bic_amb_espais_son_valids(self):
        bank = self.bank(iban='ES91 2100 0418 4502 0005 1332', swift='caix esbb xxx')
        self.assertEqual(get_company_bank_issues(bank), [])

    def test_falten_iban_bic_i_identificador(self):
        bank = self.bank(iban=None, swift='', sepa_cred_identifier=None)
        self.assertEqual(get_company_bank_issues(bank), [ISSUE_IBAN, ISSUE_BIC, ISSUE_CREDITOR_ID])

    def test_iban_i_bic_no_valids(self):
        bank = self.bank(iban='ES9121000418450200051333', swift='CAIX')
        self.assertEqual(get_company_bank_issues(bank), [ISSUE_INVALID_IBAN, ISSUE_INVALID_BIC])

    def test_empresa_sense_nif(self):
        self.company.vat = ''
        self.company.save()
        self.assertEqual(get_company_bank_issues(self.bank()), [ISSUE_COMPANY_VAT])

    def test_compte_sense_empresa(self):
        self.assertIn(ISSUE_NO_COMPANY, get_company_bank_issues(self.bank(company=None)))

    def test_el_missatge_diu_el_compte_i_el_que_falta(self):
        bank = self.bank(iban=None)
        with self.assertRaises(RemittanceBankDataError) as ctx:
            check_company_banks([self.bank(), bank])
        self.assertEqual([item['bank'] for item in ctx.exception.bank_issues], [bank.id])
        message = ctx.exception.bank_issues[0]['message']
        self.assertIn('Entitat', message)
        self.assertIn('Empresa', message)
        self.assertIn('IBAN', message)


class TestRemittanceGenerationBlocked(TestCase):
    """No es genera cap fitxer de transferències amb un compte sense les dades
    que calen. Les remeses de rebuts SEPA no es comproven."""

    def setUp(self):
        company = Company.objects.create(name='Empresa', alias='Empresa', vat='B00000000')
        self.bank = CompanyBank.objects.create(
            company=company, iban=None, swift='CAIXESBBXXX',
            sepa_cred_identifier='ES00000B00000000', is_active=True, is_default=True)
        user = get_user_model().objects.create_superuser('admin', 'admin@example.com', 'pwd')
        self.client = APIClient()
        self.client.force_authenticate(user)

    @mock.patch('billing.tasks.generate_sepa_document.apply_async')
    def test_generar_la_remesa_de_transferencies(self, apply_async):
        response = self.client.put(
            '/billing/sepa-document-generate/',
            {'create_doc': True, 'selected_bank': self.bank.id, 'payments_type': 'return'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['bank_issues'][0]['bank'], self.bank.id)
        self.assertEqual(data['bank_issues'][0]['issues'], [ISSUE_IBAN])
        self.assertIn('IBAN', data['error'])
        apply_async.assert_not_called()

    @mock.patch('billing.tasks.generate_sepa_document.apply_async')
    def test_la_remesa_de_rebuts_no_es_comprova(self, apply_async):
        apply_async.return_value = mock.Mock(id='task')
        response = self.client.put(
            '/billing/sepa-document-generate/',
            {'create_doc': True, 'selected_bank': self.bank.id, 'payments_type': 'invoice'},
            format='json',
        )
        self.assertEqual(response.status_code, 202)
        apply_async.assert_called_once()

    def remittance(self, is_return):
        status, _ = PaymentRemittanceStatus.objects.get_or_create(token='check_pending', defaults={'is_default': True})
        for token, value in (
            ('payment_remittance_status_sent_token', 'check_sent'),
            ('payment_remittance_status_processing_token', 'check_pending'),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})
        remittance = PaymentRemittance.objects.create(company_bank=self.bank, status=status, is_return=is_return)
        remittance.payments.add(Payment.objects.create(amount=10))
        return remittance

    @mock.patch('billing.tasks.regenerate_sepa_file.delay')
    def test_regenerar_el_fitxer_de_transferencies(self, delay):
        remittance = self.remittance(is_return=True)

        response = self.client.post(f'/billing/payment-remittance/{remittance.id}/sepa-document-generate/', {})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['bank_issues'][0]['issues'], [ISSUE_IBAN])
        delay.assert_not_called()

    @mock.patch('billing.tasks.regenerate_sepa_file.delay')
    def test_regenerar_el_fitxer_de_rebuts_no_es_comprova(self, delay):
        delay.return_value = mock.Mock(id='task')
        remittance = self.remittance(is_return=False)

        response = self.client.post(f'/billing/payment-remittance/{remittance.id}/sepa-document-generate/', {})

        self.assertEqual(response.status_code, 202)
        delay.assert_called_once()
