from datetime import date
from unittest.mock import patch

from django.test import TestCase

from billing.models import Billing, Invoice, InvoiceStatus, InvoiceWarning, Reading
from billing.utils.pending_termination_service import (
    PendingTerminationTransferError,
    bill_invoice_to_successor,
    get_successor_contract,
    outgoing_contract_ids_for_supply_point,
    pending_termination_warning_for,
)
from billing.utils.reading_service import copy_new_reading_to_all, resolve_reading_document_target_contract
from contract.models import (
    Contract, ContractRequest, ContractStatus, ContractTerminationRequest, ContractTerminationStatus,
)
from coredata.models import ConfigProject
from service.models import Company, Meter, MeterStatus, SupplyPoint, SupplyPointStatus


class PendingTerminationTestBase(TestCase):
    """Canvi de titular: el contracte de sortida té la baixa pendent i l'alta nova ja és
    activa al mateix punt. Tots dos contractes són actius fins que es tanca la baixa."""

    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('contract_active_token', 'ACTIVE'),
            ('contract_terminated_status', 'TERMINATED'),
            ('contract_termination_draft', 'T_DRAFT'),
            ('contract_termination_pending_token', 'T_PENDING'),
            ('contract_termination_completed_token', 'T_DONE'),
            ('invoice_status_pending_token', 'PENDING'),
            ('invoice_warning_pending_termination', 'pending_termination'),
            ('order_status_completed_token', 'ORDER_DONE'),
            ('invoice_status_paid_token', 'PAID'),
            ('invoice_status_cancelled_token', 'CANCELLED'),
            ('invoice_status_expired_token', 'EXPIRED'),
            ('bail_status_returned_token', 'RETURNED'),
            ('direct_debit_token', 'DIRECT_DEBIT'),
            ('payment_status_paid_token', 'PAID'),
            ('payment_status_cancelled_token', 'CANCELLED'),
            ('payment_status_expired_token', 'EXPIRED'),
            ('payment_status_returned_token', 'RETURNED'),
            ('payment_status_sent_token', 'SENT'),
            ('commitment_deposit_status_cancelled_token', 'CANCELLED'),
            ('payment_commitment_status_cancelled_token', 'CANCELLED'),
            ('payment_commitment_status_paid_token', 'PAID'),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})
        cls.active, _ = ContractStatus.objects.get_or_create(token='ACTIVE', defaults={'name': 'Alta'})
        ContractStatus.objects.get_or_create(token='TERMINATED', defaults={'name': 'Baixa'})
        cls.t_pending, _ = ContractTerminationStatus.objects.get_or_create(token='T_PENDING', defaults={'name': 'Pendent'})
        cls.t_done, _ = ContractTerminationStatus.objects.get_or_create(token='T_DONE', defaults={'name': 'Finalitzat'})
        cls.sp_status, _ = SupplyPointStatus.objects.get_or_create(token='SP_ACTIVE', defaults={'name': 'Actiu'})
        cls.meter_status, _ = MeterStatus.objects.get_or_create(token='1', defaults={'name': 'Actiu'})
        cls.company = Company.objects.create(name='Company pending termination')
        cls.warning, _ = InvoiceWarning.objects.get_or_create(
            token='pending_termination', defaults={'name': 'Contracte amb baixa pendent'},
        )
        cls.prefactura, _ = InvoiceStatus.objects.get_or_create(token='PENDING', defaults={'name': 'Pre-factura'})

    def setUp(self):
        self.meter = Meter.objects.create(code='PT-1', status=self.meter_status)
        self.sp = SupplyPoint.objects.create(token='PT-SP-1', meter=self.meter, status=self.sp_status)
        self.old = Contract.objects.create(
            company=self.company, token='PT-OLD', status=self.active, is_active=True,
            supply_point_default=self.sp, registration_date=date(2020, 1, 1),
        )
        self.old.supply_points.add(self.sp)
        self.termination = ContractTerminationRequest.objects.create(contract=self.old, status=self.t_pending)
        self.request = ContractRequest.objects.create(token='PT-REQ')
        self.request.contract_termination_requests.add(self.termination)
        self.new = Contract.objects.create(
            company=self.company, token='PT-NEW', status=self.active, is_active=True,
            supply_point_default=self.sp, registration_date=date(2026, 11, 13),
            contract_request=self.request,
        )
        self.new.supply_points.add(self.sp)

    def _reading(self, contract, reading_date, value, **extra):
        return Reading.objects.create(
            token='PT', contract=contract, supply_point=self.sp, meter=self.meter,
            reading_date=reading_date, reading_value=value, calculated_value=extra.pop('calculated_value', 0),
            **extra,
        )


class TestPendingTerminationDetection(PendingTerminationTestBase):

    def test_successor_is_the_contract_of_the_linked_request(self):
        self.assertEqual(get_successor_contract(self.old), self.new)
        self.assertIsNone(get_successor_contract(self.new))

    def test_warning_only_while_the_termination_is_open(self):
        self.assertEqual(pending_termination_warning_for(self.old), self.warning)
        self.assertIsNone(pending_termination_warning_for(self.new))
        self.termination.status = self.t_done
        self.termination.save()
        self.assertIsNone(pending_termination_warning_for(self.old))

    def test_outgoing_only_from_the_new_registration_date(self):
        self.assertEqual(outgoing_contract_ids_for_supply_point(self.sp, date(2027, 1, 15)), {self.old.id})
        self.assertEqual(outgoing_contract_ids_for_supply_point(self.sp, date(2026, 10, 22)), set())


class TestReadingContractWithPendingTermination(PendingTerminationTestBase):

    def test_imported_reading_after_the_new_registration_goes_to_the_new_contract(self):
        self.assertEqual(resolve_reading_document_target_contract(self.sp, date(2027, 1, 15)), self.new)

    def test_imported_reading_before_the_new_registration_stays_on_the_old_contract(self):
        self.assertEqual(resolve_reading_document_target_contract(self.sp, date(2026, 10, 22)), self.old)

    def test_closed_termination_keeps_the_usual_choice(self):
        # Sense baixa iniciada no es toca el criteri de sempre entre contractes actius.
        self.termination.status = self.t_done
        self.termination.save()
        self.assertEqual(resolve_reading_document_target_contract(self.sp, date(2027, 1, 15)), self.old)

    def test_manual_reading_is_not_copied_to_the_outgoing_contract(self):
        reading = self._reading(self.new, date(2027, 1, 15), 1300)
        copy_new_reading_to_all(reading, has_future_reading=False)
        self.assertFalse(Reading.objects.filter(contract=self.old, reading_date=date(2027, 1, 15)).exists())


class TestBillInvoiceToSuccessor(PendingTerminationTestBase):

    def setUp(self):
        super().setUp()
        self.billing = Billing.objects.create(name='Trimestral')
        self.last_billed = self._reading(self.old, date(2026, 10, 22), 1281)
        self.cut = self._reading(self.old, date(2026, 11, 13), 1284, previous_reading=self.last_billed)
        self.initial = self._reading(self.new, date(2026, 11, 13), 1284, is_initial=True)
        self.reading = self._reading(self.old, date(2027, 1, 15), 1300, previous_reading=self.cut, calculated_value=16)
        self.invoice = self._invoice([self.reading])

    def _invoice(self, readings):
        invoice = Invoice.objects.create(
            contract=self.old, billing=self.billing, status=self.prefactura, warning=self.warning, total_final=10,
        )
        invoice.readings.set(readings)
        return invoice

    def _fake_generate(self, contract, readings, title, billing=None, **kwargs):
        invoice = Invoice.objects.create(contract=contract, billing=billing, status=self.prefactura, total_final=10)
        invoice.readings.set(readings)
        return invoice

    def _bill(self, invoice):
        with patch(
            'billing.utils.invoice_service.generate_consumption_invoice_multiple', side_effect=self._fake_generate,
        ), patch('billing.utils.recalculate_invoice_service._get_invoice_warning', return_value=None):
            return bill_invoice_to_successor(invoice.id)

    def test_moves_the_readings_and_bills_the_new_contract(self):
        new_invoice = self._bill(self.invoice)

        self.assertFalse(Invoice.objects.filter(id=self.invoice.id).exists())
        self.assertEqual(new_invoice.contract, self.new)
        self.assertEqual(new_invoice.billing, self.billing)
        self.reading.refresh_from_db()
        self.assertEqual(self.reading.contract, self.new)
        self.assertEqual(self.reading.previous_reading, self.initial)
        self.assertEqual(list(new_invoice.readings.all()), [self.reading])

    def test_refuses_consumption_from_before_the_new_registration(self):
        self.reading.previous_reading = self.last_billed
        self.reading.save()
        with self.assertRaises(PendingTerminationTransferError) as ctx:
            self._bill(self.invoice)
        self.assertEqual(ctx.exception.code, 'consumption_before_successor')
        self.assertTrue(Invoice.objects.filter(id=self.invoice.id).exists())
        self.reading.refresh_from_db()
        self.assertEqual(self.reading.contract, self.old)

    def test_refuses_readings_dated_before_the_new_initial_reading(self):
        invoice = self._invoice([self.last_billed])
        with self.assertRaises(PendingTerminationTransferError) as ctx:
            self._bill(invoice)
        self.assertEqual(ctx.exception.code, 'reading_before_successor')

    def test_refuses_when_the_invoice_is_no_longer_a_pre_invoice(self):
        confirmed, _ = InvoiceStatus.objects.get_or_create(token='CONFIRMED', defaults={'name': 'Confirmada'})
        self.invoice.status = confirmed
        self.invoice.save()
        with self.assertRaises(PendingTerminationTransferError) as ctx:
            self._bill(self.invoice)
        self.assertEqual(ctx.exception.code, 'not_pre_invoice')

    def test_refuses_when_the_termination_is_already_closed(self):
        self.termination.status = self.t_done
        self.termination.save()
        with self.assertRaises(PendingTerminationTransferError) as ctx:
            self._bill(self.invoice)
        self.assertEqual(ctx.exception.code, 'no_open_termination')
