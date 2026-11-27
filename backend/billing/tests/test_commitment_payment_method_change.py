from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient
from django.test import TestCase

from billing.models import (
    CommitmentDeposit, CommitmentDepositStatus, GeneralPayment, JoinedPayment, JoinedPaymentStatus, Payment,
    PaymentCommitment, PaymentCommitmentStatus, PaymentMovement, PaymentRemittance, PaymentStatus,
)
from contract.models import Contract, PaymentType
from coredata.models import ConfigProject, Person, PersonBank
from logger.models import LogPaymentStatusChange
from service.models import Company, CompanyBank


class CommitmentPaymentMethodChangeTests(TestCase):
    """Canvi de la forma de pagament d'un rebut pendent d'un compromís de pagament."""

    @classmethod
    def setUpTestData(cls):
        cls.payment_status = {}
        for config_token, token in {
            'payment_status_paid_token': '0',
            'payment_status_pending_token': '1',
        }.items():
            ConfigProject.objects.update_or_create(token=config_token, defaults={'value': token})
            cls.payment_status[token] = PaymentStatus.objects.create(token=token, name=token)
        for config_token, value in {
            'joined_payment_status_paid_token': 'JP_PAID',
            'joined_payment_status_cancelled_token': 'JP_CANCELLED',
            'contract_terminated_status': '0',
        }.items():
            ConfigProject.objects.update_or_create(token=config_token, defaults={'value': value})
        cls.joined_status = {
            token: JoinedPaymentStatus.objects.create(token=token, name=token)
            for token in ('JP_PENDING', 'JP_PAID', 'JP_CANCELLED')
        }
        cls.deposit_status = CommitmentDepositStatus.objects.create(token='CD_PENDING', name='CD_PENDING')
        cls.pc_confirmed = PaymentCommitmentStatus.objects.create(token='PC_CONFIRMED', name='PC_CONFIRMED')

        cls.direct_debit = PaymentType.objects.create(token='DIRECT_DEBIT', name='Domiciliació')
        cls.bank_transfer = PaymentType.objects.create(token='BANK_TRANSFER', name='Transferència')
        cls.cash = PaymentType.objects.create(token='CASH', name='Efectiu')
        cls.balance = PaymentType.objects.create(token='BALANCE', name='Saldo')

        cls.company = Company.objects.create(name='Empresa A')
        cls.other_company = Company.objects.create(name='Empresa B')
        cls.company_bank = CompanyBank.objects.create(company=cls.company, iban='ES1100000000000000000001', swift='AAAAESBB')
        cls.inactive_company_bank = CompanyBank.objects.create(
            company=cls.company, iban='ES2200000000000000000002', swift='CCCCESDD', is_active=False)
        cls.other_company_bank = CompanyBank.objects.create(
            company=cls.other_company, iban='ES3300000000000000000003', swift='EEEEESFF')

        cls.holder = Person.objects.create(token='HOLDER', name='Titular')
        cls.stranger = Person.objects.create(token='STRANGER', name='Altra')
        cls.holder_bank = PersonBank.objects.create(person=cls.holder, iban='ES4400000000000000000004', swift='GGGGESHH')
        cls.holder_bank_2 = PersonBank.objects.create(person=cls.holder, iban='ES5500000000000000000005', swift='IIIIESJJ')
        cls.stranger_bank = PersonBank.objects.create(person=cls.stranger, iban='ES6600000000000000000006', swift='KKKKESLL')

        cls.user = User.objects.create_superuser('admin2917', 'admin2917@example.com', 'x')

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        general_payment = GeneralPayment.objects.create(type=self.direct_debit, IBAN=self.holder_bank)
        self.contract = Contract.objects.create(
            token='C-2917', holder=self.holder, company=self.company, payment=general_payment)
        self.deposit = CommitmentDeposit.objects.create(
            token='CP2917', contract=self.contract, status=self.deposit_status, total=Decimal('200.00'),
            remaining=Decimal('200.00'))
        self.guide = PaymentCommitment.objects.create(
            token='CP29171', commitment_deposit=self.deposit, is_guide=True, amount=Decimal('100.00'),
            currently_paid=Decimal('0.00'), due_date=date(2026, 12, 1), status=self.pc_confirmed,
            payment_type=self.direct_debit, payment_bank=self.holder_bank,
            payment_bank_final=self.holder_bank.iban, payment_swift_final=self.holder_bank.swift)
        self.other_guide = PaymentCommitment.objects.create(
            token='CP29172', commitment_deposit=self.deposit, is_guide=True, amount=Decimal('100.00'),
            currently_paid=Decimal('0.00'), due_date=date(2027, 1, 1), status=self.pc_confirmed,
            payment_type=self.direct_debit, payment_bank=self.holder_bank)
        self.payment = Payment.objects.create(
            token='CP291701', commitment_deposit=self.deposit, contract=self.contract,
            amount=Decimal('100.00'), status=self.payment_status['1'],
            payment_type=self.direct_debit.name, payment_type_token='DIRECT_DEBIT',
            payment_bank=self.holder_bank.iban, payment_swift=self.holder_bank.swift,
            due_date=date(2026, 12, 1), is_marked_for_remittance=True)

    def change(self, payment_type, **extra):
        return self.client.put(
            reverse('payment-change-commitment-payment-method', args=[self.payment.id]),
            {'payment_type_id': payment_type.id, **extra}, format='json')

    def test_direct_debit_to_transfer_updates_receipt_and_commitment_term(self):
        response = self.change(self.bank_transfer, company_bank_id=self.company_bank.id)

        self.assertEqual(response.status_code, 200, response.data)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.payment_type_token, 'BANK_TRANSFER')
        self.assertEqual(self.payment.payment_type, self.bank_transfer.name)
        self.assertEqual(self.payment.payment_bank, self.company_bank.iban)
        self.assertEqual(self.payment.payment_swift, self.company_bank.swift)
        self.assertFalse(self.payment.is_marked_for_remittance)
        # Sense moviments ni canvi d'estat
        self.assertEqual(self.payment.status, self.payment_status['1'])
        self.assertFalse(PaymentMovement.objects.filter(payment=self.payment).exists())

        self.guide.refresh_from_db()
        self.assertEqual(self.guide.payment_type, self.bank_transfer)
        self.assertIsNone(self.guide.payment_bank)
        self.assertEqual(self.guide.payment_bank_final, self.company_bank.iban)
        self.other_guide.refresh_from_db()
        self.assertEqual(self.other_guide.payment_type, self.direct_debit)

        log = LogPaymentStatusChange.objects.get(object=self.payment)
        self.assertEqual(log.previous_status, self.payment_status['1'])
        self.assertEqual(log.current_status, self.payment_status['1'])
        self.assertEqual(log.user, self.user)
        self.assertIn(self.bank_transfer.name, log.observation)
        self.assertIn('marcat per remesar', log.observation)

    def test_transfer_requires_an_active_bank_of_the_contract_company(self):
        for company_bank_id in (None, self.inactive_company_bank.id, self.other_company_bank.id):
            response = self.change(self.bank_transfer, company_bank_id=company_bank_id)
            self.assertEqual(response.status_code, 400)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.payment_type_token, 'DIRECT_DEBIT')
        self.assertFalse(LogPaymentStatusChange.objects.filter(object=self.payment).exists())

    def test_to_direct_debit_uses_a_bank_of_the_contract_persons(self):
        Payment.objects.filter(id=self.payment.id).update(payment_type='Efectiu', payment_type_token='CASH')

        self.assertEqual(self.change(self.direct_debit, person_bank_id=self.stranger_bank.id).status_code, 400)

        response = self.change(self.direct_debit, person_bank_id=self.holder_bank_2.id)
        self.assertEqual(response.status_code, 200, response.data)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.payment_bank, self.holder_bank_2.iban)
        self.guide.refresh_from_db()
        self.assertEqual(self.guide.payment_bank, self.holder_bank_2)

    def test_to_direct_debit_defaults_to_the_contract_direct_debit_bank(self):
        Payment.objects.filter(id=self.payment.id).update(payment_type='Efectiu', payment_type_token='CASH')

        response = self.change(self.direct_debit)

        self.assertEqual(response.status_code, 200, response.data)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.payment_bank, self.holder_bank.iban)

    def test_paid_receipt_cannot_change(self):
        Payment.objects.filter(id=self.payment.id).update(status=self.payment_status['0'])

        self.assertEqual(self.change(self.cash).status_code, 400)

    def test_receipt_in_pending_remittance_cannot_change(self):
        remittance = PaymentRemittance.objects.create(token='REM')
        remittance.payments.add(self.payment)

        self.assertEqual(self.change(self.cash).status_code, 400)

        remittance.sent_at = date(2026, 11, 20)
        remittance.save()
        self.assertEqual(self.change(self.cash).status_code, 200)

    def test_receipt_in_open_joined_payment_cannot_change(self):
        joined = JoinedPayment.objects.create(token='JP', status=self.joined_status['JP_PENDING'])
        joined.payments.add(self.payment)

        self.assertEqual(self.change(self.cash).status_code, 400)

        joined.status = self.joined_status['JP_CANCELLED']
        joined.save()
        self.assertEqual(self.change(self.cash).status_code, 200)

    def test_balance_and_same_method_are_rejected(self):
        self.assertEqual(self.change(self.balance).status_code, 400)
        self.assertEqual(self.change(self.direct_debit).status_code, 400)

    def test_invoice_receipt_cannot_change_here(self):
        from billing.models import Invoice
        # bulk_create: sense els senyals de la factura, que aquí no calen
        invoice = Invoice.objects.bulk_create([Invoice(token='F-2917')])[0]
        Payment.objects.filter(id=self.payment.id).update(invoice=invoice)

        self.assertEqual(self.change(self.cash).status_code, 400)

    def test_options_list_methods_and_banks(self):
        response = self.client.get(reverse('payment-commitment-payment-method-options', args=[self.payment.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['can_change'])
        tokens = {pt['token'] for pt in response.data['payment_types']}
        self.assertNotIn('BALANCE', tokens)
        self.assertIn('BANK_TRANSFER', tokens)
        self.assertEqual([b['id'] for b in response.data['company_banks']], [self.company_bank.id])
        person_banks = {b['id']: b for b in response.data['person_banks']}
        self.assertEqual(set(person_banks), {self.holder_bank.id, self.holder_bank_2.id})
        self.assertTrue(person_banks[self.holder_bank.id]['is_default'])
