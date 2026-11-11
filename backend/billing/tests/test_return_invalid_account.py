import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from billing.models import GeneralPayment, Invoice, Payment, PaymentRemittance, RejectMotive
from billing.tests.test_return_after_payment_method_change import ReturnAfterPaymentMethodChangeBase
from billing.utils.payment_service import generate_payment_movement
from billing.utils.sepa_invalid_account_service import (
    INVALID_ACCOUNT_CONFIG_TOKEN, get_invalid_account_reject_tokens, invalid_account_payment_alert,
    is_invalid_account_reject_token,
)
from billing.utils.sepa_service import handle_not_found_payment
from contract.models import Contract, ContractDataChange, PaymentType
from contract.serializers.contract_pinned_serializer import PinnedContractSerializer
from contract.serializers.contract_serializer import ContractSerializer
from coredata.models import ConfigProject, Person, PersonBank
from logger.models import LogInvoiceDataChange

INVALID_IBAN = 'ES0000000000000000000000'
OTHER_IBAN = 'ES1111111111111111111111'
DEFAULT_TOKENS = ['AC01', 'AC04', 'AC06', 'AC13', 'AG01', 'BE06', 'MD07', 'RC01']


class TestInvalidAccountTokens(TestCase):

    def set_config(self, value):
        ConfigProject.objects.update_or_create(token=INVALID_ACCOUNT_CONFIG_TOKEN, defaults={'value': value})

    def test_tokens_are_normalized(self):
        self.set_config(' ac04, AC06 ,,be06 ')

        self.assertEqual(get_invalid_account_reject_tokens(), {'AC04', 'AC06', 'BE06'})
        self.assertTrue(is_invalid_account_reject_token('ac04 '))
        self.assertFalse(is_invalid_account_reject_token('AM04'))
        self.assertFalse(is_invalid_account_reject_token(None))

    def test_missing_or_empty_config_disables_the_feature(self):
        # La migració de dades el crea: aquí es prova l'absència del paràmetre
        ConfigProject.objects.filter(token=INVALID_ACCOUNT_CONFIG_TOKEN).delete()
        self.assertEqual(get_invalid_account_reject_tokens(), set())
        self.assertFalse(is_invalid_account_reject_token('AC04'))
        self.set_config('')
        self.assertFalse(is_invalid_account_reject_token('AC04'))

    def test_default_fixtures_include_all_invalid_account_codes(self):
        for lang in ('ca', 'es'):
            path = Path(settings.BASE_DIR) / 'initial_data' / lang / 'config_project' / 'local' / 'ConfigProject.json'
            entries = [e for e in json.loads(path.read_text()) if e['fields']['token'] == INVALID_ACCOUNT_CONFIG_TOKEN]
            self.assertEqual(len(entries), 1, lang)
            fields = entries[0]['fields']
            self.assertEqual(fields['value'].split(','), DEFAULT_TOKENS, lang)
            # El nom documenta cada codi per als administradors
            for token in DEFAULT_TOKENS:
                self.assertIn(token, fields['name'], lang)
            self.assertLessEqual(len(fields['name']), 255, lang)


class InvalidAccountReturnBase(ReturnAfterPaymentMethodChangeBase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.bank_payment = PaymentType.objects.create(token='BANK_PAYMENT', name='Pagament Bancari')
        ConfigProject.objects.update_or_create(token='bank_payment_token', defaults={'value': 'BANK_PAYMENT'})
        ConfigProject.objects.update_or_create(
            token=INVALID_ACCOUNT_CONFIG_TOKEN, defaults={'value': ','.join(DEFAULT_TOKENS)})
        cls.invalid_motive = RejectMotive.objects.create(token='AC04', name='Compte tancat')

    def setUp(self):
        super().setUp()
        self.holder = Person.objects.create(name='Titular', surname='Prova', token='00000000T')
        # Desat amb espais: la comparació d'IBAN no en depèn
        self.person_bank = PersonBank.objects.create(
            person=self.holder, iban='ES00 0000 0000 0000 0000 0000', swift='TESTESBB', is_default=True)
        self.general_payment = GeneralPayment.objects.create(
            token='GP-RET', type=self.direct_debit, IBAN=self.person_bank, mandate_id='MANDATE')
        self.contract.holder = self.holder
        self.contract.payment = self.general_payment
        self.contract.save()

    def create_invoice(self, token, invoice_status, payment_status, iban=INVALID_IBAN):
        invoice = Invoice.objects.create(
            token=token, contract=self.contract, serie_final=f'FC/{token}',
            status=self.invoice_status[invoice_status], due_date=date(2026, 12, 31),
            payment_type_final='Domiciliació', payment_type_token_final='DIRECT_DEBIT',
            payment_bank_final=iban, payment_swift_final='TESTESBB')
        payment = Payment.objects.create(
            token=f'P{token}', amount=Decimal('10.00'), invoice=invoice,
            status=self.payment_status[payment_status], payment_type='Domiciliació',
            payment_type_token='DIRECT_DEBIT', payment_bank=iban, payment_swift='TESTESBB',
            due_date=date(2026, 12, 31))
        return invoice, payment

    def post_return(self, motive):
        client = APIClient()
        client.force_authenticate(self.user)
        rejection = {
            'id': self.payment.id, 'skip_return': False, 'rjt_dt': '2026-09-09',
            'motive_id': motive.id, 'motive': motive.name,
        }
        data = {
            'payments_to_return': json.dumps([rejection]),
            'return_payments': json.dumps([]),
            'claim_payments': json.dumps([]),
            'return_date': '2026-09-09',
        }
        # La factura de despeses de devolució no és l'objecte d'aquestes proves
        with mock.patch('billing.views.payment_view.invoice_return_charge') as return_charge:
            return_charge.return_value = mock.MagicMock()
            return client.post(reverse('payment-manage-rejection-payments'), data, format='multipart')

    def assert_direct_debit_kept(self):
        self.person_bank.refresh_from_db()
        self.general_payment.refresh_from_db()
        self.contract.refresh_from_db()
        self.assertTrue(self.person_bank.is_active)
        self.assertTrue(self.general_payment.is_active)
        self.assertEqual(self.contract.payment_id, self.general_payment.id)
        self.assertFalse(ContractDataChange.objects.filter(contract=self.contract).exists())

    def assert_invoice_is_bank_payment(self, invoice, payment):
        invoice.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(invoice.payment_type_token_final, 'BANK_PAYMENT')
        self.assertEqual(invoice.payment_type_final, 'Pagament Bancari')
        self.assertIsNone(invoice.payment_bank_final)
        self.assertIsNone(invoice.payment_swift_final)
        self.assertEqual(payment.payment_type_token, 'BANK_PAYMENT')
        self.assertIsNone(payment.payment_bank)
        self.assertIsNone(payment.payment_swift)
        log = LogInvoiceDataChange.objects.get(object=invoice)
        self.assertEqual(log.current_payment_type, 'Pagament Bancari')
        self.assertEqual(log.previous_payment_type, 'Domiciliació')
        self.assertEqual(log.user, self.user)

    def assert_invoice_is_direct_debit(self, invoice, payment, iban=INVALID_IBAN):
        invoice.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(invoice.payment_type_token_final, 'DIRECT_DEBIT')
        self.assertEqual(invoice.payment_bank_final, iban)
        self.assertEqual(payment.payment_type_token, 'DIRECT_DEBIT')
        self.assertEqual(payment.payment_bank, iban)
        self.assertFalse(LogInvoiceDataChange.objects.filter(object=invoice).exists())


class TestManageInvalidAccountReturn(InvalidAccountReturnBase):

    def test_invalid_account_return_deactivates_direct_debit(self):
        response = self.post_return(self.invalid_motive)

        self.assertEqual(response.status_code, 200)
        self.person_bank.refresh_from_db()
        self.general_payment.refresh_from_db()
        self.contract.refresh_from_db()
        self.assertFalse(self.person_bank.is_active)
        self.assertFalse(self.person_bank.is_default)
        self.assertIsNotNone(self.person_bank.deactivated_at)
        self.assertFalse(self.general_payment.is_active)

        new_payment = self.contract.payment
        self.assertNotEqual(new_payment.id, self.general_payment.id)
        self.assertEqual(new_payment.type, self.bank_payment)
        self.assertIsNone(new_payment.IBAN)
        self.assertTrue(new_payment.is_active)

        data_change = ContractDataChange.objects.get(contract=self.contract)
        self.assertEqual(data_change.previous_payment, self.person_bank)
        self.assertIsNone(data_change.new_payment)
        self.assertEqual(data_change.previous_payment_type, self.direct_debit)
        self.assertEqual(data_change.new_payment_type, self.bank_payment)
        self.assertEqual(data_change.user, self.user)

        changes = response.json()['invalid_account_changes']
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]['motive'], 'AC04')
        self.assertEqual(changes[0]['contracts'], [self.contract.token])

    def test_returned_invoice_and_pending_invoices_switch_to_bank_payment(self):
        pending_invoice, pending_payment = self.create_invoice('PEND', 'CONFIRMED', '1')
        returned_invoice, returned_payment = self.create_invoice('RETD', 'EXPIRED', '-2')

        self.post_return(self.invalid_motive)

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status.token, '-2')
        self.assert_invoice_is_bank_payment(self.invoice, self.payment)
        self.assert_invoice_is_bank_payment(pending_invoice, pending_payment)
        self.assert_invoice_is_bank_payment(returned_invoice, returned_payment)

    def test_invoice_in_unsent_remittance_is_not_changed(self):
        invoice, payment = self.create_invoice('REM', 'CONFIRMED', '1')
        remittance = PaymentRemittance.objects.create(token='REM-PENDING', sent_at=None)
        remittance.payments.add(payment)

        self.post_return(self.invalid_motive)

        self.assert_invoice_is_direct_debit(invoice, payment)

    def test_invoice_in_sent_remittance_is_changed(self):
        invoice, payment = self.create_invoice('REMS', 'CONFIRMED', '1')
        remittance = PaymentRemittance.objects.create(token='REM-SENT', sent_at=date(2026, 9, 1))
        remittance.payments.add(payment)

        self.post_return(self.invalid_motive)

        self.assert_invoice_is_bank_payment(invoice, payment)

    def test_paid_invoice_is_not_changed(self):
        invoice, payment = self.create_invoice('PAID', 'PAID', '0')

        self.post_return(self.invalid_motive)

        self.assert_invoice_is_direct_debit(invoice, payment)

    def test_invoice_with_another_iban_is_not_changed(self):
        invoice, payment = self.create_invoice('OTHR', 'CONFIRMED', '1', iban=OTHER_IBAN)

        self.post_return(self.invalid_motive)

        self.assert_invoice_is_direct_debit(invoice, payment, iban=OTHER_IBAN)

    def test_other_motive_keeps_direct_debit(self):
        invoice, payment = self.create_invoice('PEND', 'CONFIRMED', '1')

        response = self.post_return(self.motive)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['invalid_account_changes'], [])
        self.assert_direct_debit_kept()
        self.assert_invoice_is_direct_debit(invoice, payment)

    def test_empty_config_keeps_direct_debit(self):
        ConfigProject.objects.filter(token=INVALID_ACCOUNT_CONFIG_TOKEN).update(value='')
        invoice, payment = self.create_invoice('PEND', 'CONFIRMED', '1')

        self.post_return(self.invalid_motive)

        self.assert_direct_debit_kept()
        self.assert_invoice_is_direct_debit(invoice, payment)

    def test_missing_config_keeps_direct_debit(self):
        ConfigProject.objects.filter(token=INVALID_ACCOUNT_CONFIG_TOKEN).delete()

        self.post_return(self.invalid_motive)

        self.assert_direct_debit_kept()

    def test_reloading_the_return_does_not_repeat_the_cascade(self):
        self.post_return(self.invalid_motive)

        response = self.post_return(self.invalid_motive)

        self.assertEqual(response.json()['invalid_account_changes'], [])
        self.assertEqual(ContractDataChange.objects.filter(contract=self.contract).count(), 1)
        self.assertEqual(GeneralPayment.objects.filter(type=self.bank_payment).count(), 1)

    def test_another_active_bank_becomes_default(self):
        other_bank = PersonBank.objects.create(person=self.holder, iban=OTHER_IBAN, is_default=False)

        self.post_return(self.invalid_motive)

        other_bank.refresh_from_db()
        self.assertTrue(other_bank.is_active)
        self.assertTrue(other_bank.is_default)

    def test_method_changed_return_also_deactivates_direct_debit(self):
        # Cobrada per domiciliació i després canviada a efectiu: la factura continua pagada
        self.change_method_to_cash()

        self.post_return(self.invalid_motive)

        self.invoice.refresh_from_db()
        self.contract.refresh_from_db()
        self.person_bank.refresh_from_db()
        self.assertEqual(self.invoice.status.token, 'PAID')
        self.assertFalse(self.person_bank.is_active)
        self.assertEqual(self.contract.payment.type, self.bank_payment)


class TestInvalidAccountReturnPreview(InvalidAccountReturnBase):

    def parse(self, reject_token):
        client_data = {'end_to_end_id': self.payment.token, 'RJT': reject_token, 'IBAN': INVALID_IBAN}
        return handle_not_found_payment(client_data, {'name': 'EMPRESA'}, '2026-09-09')

    def test_invalid_account_code_is_flagged(self):
        self.assertTrue(self.parse('AC04')['invalid_account'])

    def test_other_code_is_not_flagged(self):
        self.assertFalse(self.parse('AM04')['invalid_account'])

    def test_empty_config_is_not_flagged(self):
        ConfigProject.objects.filter(token=INVALID_ACCOUNT_CONFIG_TOKEN).update(value='')
        self.assertFalse(self.parse('AC04')['invalid_account'])

    def test_skipped_return_is_not_flagged(self):
        # Pagada per un altre mètode sense domiciliació: el retorn no s'aplicarà
        self.payment.movements.all().delete()
        self.change_method_to_cash()
        generate_payment_movement(self.payment, self.payment_status['0'], date(2026, 9, 3), 'CASH', None, self.user)

        rejection = self.parse('AC04')

        self.assertTrue(rejection['skip_return'])
        self.assertFalse(rejection['invalid_account'])

    def test_preview_does_not_change_anything(self):
        self.parse('AC04')

        self.assert_direct_debit_kept()

    def test_unknown_payment_is_not_flagged(self):
        client_data = {'end_to_end_id': 'UNKNOWN', 'RJT': 'AC04', 'IBAN': INVALID_IBAN}
        rejection = handle_not_found_payment(client_data, {'name': 'EMPRESA'}, '2026-09-09')
        self.assertTrue(rejection['not_found'])
        self.assertFalse(rejection['invalid_account'])


class TestContractInvalidAccountAlert(InvalidAccountReturnBase):
    """Avís a la fitxa del contracte quan la domiciliació s'ha anul·lat per compte invàlid."""

    def alert(self):
        contract = Contract.objects.select_related('payment__type').get(id=self.contract.id)
        return invalid_account_payment_alert(contract)

    def test_return_records_motive_and_new_payment_in_data_change(self):
        self.post_return(self.invalid_motive)

        self.contract.refresh_from_db()
        data_change = ContractDataChange.objects.get(contract=self.contract)
        self.assertEqual(data_change.reject_motive, self.invalid_motive)
        self.assertEqual(data_change.new_general_payment_id, self.contract.payment_id)

    def test_alert_after_invalid_account_return(self):
        self.post_return(self.invalid_motive)

        alert = self.alert()

        self.assertEqual(alert['motive_token'], 'AC04')
        self.assertEqual(alert['motive_name'], self.invalid_motive.name)
        self.assertEqual(alert['previous_iban'], self.person_bank.iban)
        self.assertIsNotNone(alert['date'])

    def test_both_contract_serializers_expose_the_alert(self):
        self.post_return(self.invalid_motive)
        contract = Contract.objects.select_related('payment__type').get(id=self.contract.id)

        for serializer_class in (ContractSerializer, PinnedContractSerializer):
            alert = serializer_class().get_invalid_account_payment_alert(contract)
            self.assertEqual(alert['motive_token'], 'AC04', serializer_class.__name__)
        self.assertIn('invalid_account_payment_alert', ContractSerializer().fields)
        self.assertIn('invalid_account_payment_alert', PinnedContractSerializer().fields)

    def test_no_alert_without_invalid_account_return(self):
        self.assertIsNone(self.alert())
        self.assertIsNone(ContractSerializer().get_invalid_account_payment_alert(self.contract))

    def test_no_alert_after_other_motive(self):
        self.post_return(self.motive)

        self.assertIsNone(self.alert())

    def test_no_alert_for_manual_bank_payment(self):
        # Pagament bancari posat a mà, sense cap retorn: no és un avís de retorn
        manual = GeneralPayment.objects.create(token='GP-MANUAL', type=self.bank_payment)
        self.contract.payment = manual
        self.contract.save()

        self.assertIsNone(self.alert())

    def test_alert_clears_when_contract_gets_another_payment(self):
        self.post_return(self.invalid_motive)
        new_bank = PersonBank.objects.create(person=self.holder, iban=OTHER_IBAN)
        self.contract.payment = GeneralPayment.objects.create(token='GP-NEW', type=self.direct_debit, IBAN=new_bank)
        self.contract.save()

        self.assertIsNone(self.alert())

    def test_alert_clears_when_iban_is_added_to_the_payment(self):
        self.post_return(self.invalid_motive)
        self.contract.refresh_from_db()
        payment = self.contract.payment
        payment.IBAN = PersonBank.objects.create(person=self.holder, iban=OTHER_IBAN)
        payment.save()

        self.assertIsNone(self.alert())

    def test_alert_clears_when_payment_type_changes(self):
        self.post_return(self.invalid_motive)
        self.contract.refresh_from_db()
        GeneralPayment.objects.filter(id=self.contract.payment_id).update(type=self.cash)

        self.assertIsNone(self.alert())

    def test_alert_uses_a_bounded_number_of_queries(self):
        self.post_return(self.invalid_motive)
        contract = Contract.objects.select_related('payment__type').get(id=self.contract.id)

        # Paràmetre del tipus de pagament bancari + l'últim canvi de dades del contracte
        with self.assertNumQueries(2):
            invalid_account_payment_alert(contract)
