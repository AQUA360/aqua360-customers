import importlib
from datetime import timedelta

from django.apps import apps
from django.utils import timezone

from billing.models import Invoice, InvoiceStatus
from billing.serializers.invoice_serializer import InvoiceFullSerializer
from billing.tests.test_return_invalid_account import InvalidAccountReturnBase
from billing.utils.invoice_service import apply_invoice_payment_method
from billing.utils.payment_method_alert_service import (
    contract_remittance_blocked_alert, invoice_payment_method_alert,
)
from contract.serializers.contract_pinned_serializer import PinnedContractSerializer
from contract.serializers.contract_serializer import ContractSerializer
from coredata.models import ConfigProject
from logger.models import LogInvoiceDataChange

BLOCKED = LogInvoiceDataChange.AUTO_REASON_REMITTANCE_BLOCKED
INVALID_ACCOUNT = LogInvoiceDataChange.AUTO_REASON_INVALID_ACCOUNT_RETURN
BLOCKED_OBSERVATION = "No es domicilia: el contracte té factures pendents de cobrar"


class PaymentMethodAlertBase(InvalidAccountReturnBase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Desar una factura passa pels senyals, que llegeixen l'estat d'anul·lada
        ConfigProject.objects.update_or_create(token='invoice_status_cancelled_token', defaults={'value': 'CANCELLED'})
        ConfigProject.objects.update_or_create(token='invoice_status_dropped_token', defaults={'value': 'DROPPED'})
        cls.invoice_status['DROPPED'], _ = InvoiceStatus.objects.get_or_create(token='DROPPED', defaults={'name': 'Abonada'})

    def create_blocked_invoice(self, token, status='CONFIRMED', observation=BLOCKED_OBSERVATION, auto_reason=BLOCKED):
        """Factura nova que el procés de facturació ha passat a pagament bancari (com fa invoice_service)."""
        invoice = Invoice.objects.create(
            token=token, contract=self.contract, serie_final=f'FC/{token}',
            status=self.invoice_status[status],
            payment_type_final=self.bank_payment.name, payment_type_token_final=self.bank_payment.token)
        LogInvoiceDataChange.objects.create(
            object=invoice, previous_payment_type=self.direct_debit.name,
            current_payment_type=self.bank_payment.name, observation=observation,
            auto_reason=auto_reason, user=None, timestamp=timezone.now())
        return invoice


class TestInvoiceAlertAfterInvalidAccountReturn(PaymentMethodAlertBase):

    def test_invoice_changed_by_the_return_shows_the_alert(self):
        invoice, _payment = self.create_invoice('PEND', 'CONFIRMED', '1')

        self.post_return(self.invalid_motive)

        log = LogInvoiceDataChange.objects.get(object=invoice)
        self.assertEqual(log.auto_reason, INVALID_ACCOUNT)
        self.assertEqual(log.reject_motive, self.invalid_motive)
        invoice.refresh_from_db()
        alert = invoice_payment_method_alert(invoice)
        self.assertEqual(alert['reason'], INVALID_ACCOUNT)
        self.assertEqual(alert['motive_token'], 'AC04')
        self.assertEqual(alert['motive_name'], self.invalid_motive.name)
        self.assertEqual(alert['previous_payment_type'], 'Domiciliació')
        self.assertIsNotNone(alert['date'])
        self.assertEqual(InvoiceFullSerializer().get_payment_method_alert(invoice)['reason'], INVALID_ACCOUNT)
        # El contracte té el seu propi avís de compte invàlid; aquest és només el del bloqueig
        self.assertIsNone(contract_remittance_blocked_alert(self.contract))

    def test_alert_clears_when_the_invoice_is_changed_again(self):
        invoice, _payment = self.create_invoice('PEND', 'CONFIRMED', '1')
        self.post_return(self.invalid_motive)
        invoice.refresh_from_db()

        apply_invoice_payment_method(self.user, invoice, self.direct_debit, 'ES2222222222222222222222', 'TESTESBB')

        invoice.refresh_from_db()
        self.assertIsNone(invoice_payment_method_alert(invoice))

    def test_other_motive_shows_no_alert(self):
        invoice, _payment = self.create_invoice('PEND', 'CONFIRMED', '1')

        self.post_return(self.motive)

        invoice.refresh_from_db()
        self.assertIsNone(invoice_payment_method_alert(invoice))


class TestRemittanceBlockedAlert(PaymentMethodAlertBase):

    def test_blocked_invoice_shows_the_alert_on_invoice_and_contract(self):
        invoice = self.create_blocked_invoice('BLK1')

        alert = invoice_payment_method_alert(invoice)
        self.assertEqual(alert['reason'], BLOCKED)
        self.assertIsNone(alert['motive_token'])
        self.assertEqual(alert['previous_payment_type'], self.direct_debit.name)

        contract_alert = contract_remittance_blocked_alert(self.contract)
        self.assertEqual(contract_alert['count'], 1)
        self.assertEqual(contract_alert['invoices'], [{'id': invoice.id, 'number': 'FC/BLK1'}])
        self.assertIsNotNone(contract_alert['date'])

    def test_both_contract_serializers_expose_the_alert(self):
        self.create_blocked_invoice('BLK1')

        for serializer_class in (ContractSerializer, PinnedContractSerializer):
            self.assertIn('remittance_blocked_alert', serializer_class().fields)
            alert = serializer_class().get_remittance_blocked_alert(self.contract)
            self.assertEqual(alert['count'], 1, serializer_class.__name__)
        self.assertIn('payment_method_alert', InvoiceFullSerializer().fields)

    def test_paid_or_inactive_invoices_are_not_counted(self):
        self.create_blocked_invoice('BLK1')
        self.create_blocked_invoice('BLK2', status='PAID')
        self.create_blocked_invoice('BLK4', status='DROPPED')
        inactive = self.create_blocked_invoice('BLK3')
        Invoice.objects.filter(id=inactive.id).update(is_active=False)

        self.assertEqual(contract_remittance_blocked_alert(self.contract)['count'], 1)

    def test_alert_clears_when_the_invoice_is_set_back_to_direct_debit(self):
        invoice = self.create_blocked_invoice('BLK1')

        apply_invoice_payment_method(self.user, invoice, self.direct_debit, 'ES2222222222222222222222', 'TESTESBB')

        invoice.refresh_from_db()
        self.assertIsNone(invoice_payment_method_alert(invoice))
        self.assertIsNone(contract_remittance_blocked_alert(self.contract))

    def test_manual_change_shows_no_alert(self):
        invoice = self.create_blocked_invoice('MAN1', observation=None, auto_reason=None)

        self.assertIsNone(invoice_payment_method_alert(invoice))
        self.assertIsNone(contract_remittance_blocked_alert(self.contract))

    def test_only_the_last_payment_type_change_counts(self):
        invoice = self.create_blocked_invoice('BLK1')
        # Un canvi posterior a mà que torna a deixar el mateix mètode: ja no és del sistema
        LogInvoiceDataChange.objects.create(
            object=invoice, previous_payment_type=self.bank_payment.name,
            current_payment_type=self.bank_payment.name, user=self.user,
            timestamp=timezone.now() + timedelta(minutes=1))

        self.assertIsNone(invoice_payment_method_alert(invoice))

    def test_change_through_the_invoice_update_is_logged(self):
        invoice = self.create_blocked_invoice('BLK1')
        request = type('Request', (), {'user': self.user})()
        serializer = InvoiceFullSerializer(context={'request': request})

        # Es canvia a mà a domiciliació i es torna a pagament bancari, per l'actualització de la factura
        serializer.update(invoice, {'payment_type_final': self.direct_debit.name})
        serializer.update(invoice, {'payment_type_final': self.bank_payment.name})

        logs = LogInvoiceDataChange.objects.filter(object=invoice, auto_reason__isnull=True)
        self.assertEqual(logs.count(), 2)
        invoice.refresh_from_db()
        self.assertIsNone(invoice_payment_method_alert(invoice))
        self.assertIsNone(contract_remittance_blocked_alert(self.contract))

    def test_no_alert_without_changes(self):
        self.assertIsNone(contract_remittance_blocked_alert(self.contract))
        self.assertIsNone(invoice_payment_method_alert(self.invoice))


class TestRemittanceBlockedBackfill(PaymentMethodAlertBase):

    def test_existing_blocked_logs_are_marked(self):
        old = self.create_blocked_invoice('OLD1', auto_reason=None)
        manual = self.create_blocked_invoice('MAN1', observation='Canvi a mà', auto_reason=None)
        migration = importlib.import_module('logger.migrations.0056_loginvoicedatachange_auto_reason')

        migration.mark_remittance_blocked_logs(apps, None)

        self.assertEqual(LogInvoiceDataChange.objects.get(object=old).auto_reason, BLOCKED)
        self.assertIsNone(LogInvoiceDataChange.objects.get(object=manual).auto_reason)
        self.assertEqual(contract_remittance_blocked_alert(self.contract)['count'], 1)
