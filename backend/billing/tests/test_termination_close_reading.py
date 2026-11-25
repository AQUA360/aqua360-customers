from datetime import date

from django.test import TestCase

from billing.models import Invoice, Reading
from billing.utils.invoice_service import (
    TerminationCloseReadingMissingError,
    invoice_contract_termination_generate,
)
from billing.utils.termination_close_reading_service import ensure_termination_close_readings
from contract.models import (
    Contract, ContractRequest, ContractStatus, ContractTerminationRequest, ContractTerminationStatus,
)
from coredata.models import ConfigProject
from service.models import Company, Meter, MeterStatus, SupplyPoint, SupplyPointStatus


class TerminationCloseReadingTestBase(TestCase):
    """Canvi de titular: la lectura de tall s'entra a l'alta com a lectura inicial."""

    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('reading_estimated', 'false'),
            ('contract_active_token', 'ACTIVE'),
            ('contract_terminated_status', 'TERMINATED'),
            ('contract_termination_draft', 'T_DRAFT'),
            ('contract_termination_pending_token', 'T_PENDING'),
            ('contract_termination_completed_token', 'T_DONE'),
            ('invoice_status_pending_token', 'PENDING'),
            ('invoice_status_paid_token', 'PAID'),
            ('invoice_status_cancelled_token', 'CANCELLED'),
            ('invoice_status_expired_token', 'EXPIRED'),
            ('bail_status_returned_token', 'RETURNED'),
            ('order_status_completed_token', 'ORDER_DONE'),
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
        cls.t_pending, _ = ContractTerminationStatus.objects.get_or_create(token='T_PENDING', defaults={'name': 'Pendent'})
        cls.sp_status, _ = SupplyPointStatus.objects.get_or_create(token='SP_ACTIVE', defaults={'name': 'Actiu'})
        cls.meter_status, _ = MeterStatus.objects.get_or_create(token='1', defaults={'name': 'Actiu'})
        cls.company = Company.objects.create(name='Company close reading')

    def setUp(self):
        self.meter = Meter.objects.create(code='CR-1', status=self.meter_status)
        self.sp = SupplyPoint.objects.create(token='CR-SP-1', meter=self.meter, status=self.sp_status)
        self.old = Contract.objects.create(
            company=self.company, token='CR-OLD', status=self.active, is_active=True,
            supply_point_default=self.sp, registration_date=date(2023, 3, 3),
        )
        self.old.supply_points.add(self.sp)
        self.termination = ContractTerminationRequest.objects.create(contract=self.old, status=self.t_pending)
        self.request = ContractRequest.objects.create(token='CR-REQ')
        self.request.contract_termination_requests.add(self.termination)
        self.billed = self._reading(self.old, date(2025, 12, 16), 120)
        invoice = Invoice.objects.create(contract=self.old, type_final='F')
        invoice.readings.add(self.billed)

    def _reading(self, contract, reading_date, value, **extra):
        return Reading.objects.create(
            token='CR', contract=contract, supply_point=self.sp, meter=self.meter,
            reading_date=reading_date, reading_value=value, calculated_value=0, **extra,
        )

    def _initial_reading(self, reading_date=date(2026, 11, 4), value=130, **extra):
        # Com la desa `request-reading/`: inicial, inactiva i sense contracte.
        return Reading.objects.create(
            contract_request=self.request, supply_point=self.sp, meter=self.meter,
            reading_date=reading_date, reading_value=value, is_initial=True, is_active=False,
            consumption_days=0, **extra,
        )


class TestEnsureTerminationCloseReadings(TerminationCloseReadingTestBase):

    def test_creates_the_close_reading_of_the_old_contract_from_the_cut_reading(self):
        self._initial_reading(leak_value=2)

        created = ensure_termination_close_readings(self.termination)

        self.assertEqual(len(created), 1)
        close = created[0]
        self.assertEqual(close.contract, self.old)
        self.assertEqual(close.reading_date, date(2026, 11, 4))
        self.assertEqual(float(close.reading_value), 130)
        self.assertEqual(float(close.calculated_value), 10)
        self.assertEqual(float(close.leak_value), 2)
        self.assertEqual(close.previous_reading, self.billed)
        self.assertEqual(close.consumption_days, 323)
        self.assertFalse(close.is_initial)
        self.assertTrue(close.is_active)
        self.assertEqual(list(self.termination.readings.all()), [close])

    def test_runs_once(self):
        self._initial_reading()
        ensure_termination_close_readings(self.termination)

        self.assertEqual(ensure_termination_close_readings(self.termination), [])
        self.assertEqual(Reading.objects.filter(contract=self.old, reading_date=date(2026, 11, 4)).count(), 1)

    def test_also_after_the_new_contract_takes_the_initial_reading(self):
        new = Contract.objects.create(
            company=self.company, token='CR-NEW', status=self.active, is_active=True,
            supply_point_default=self.sp, registration_date=date(2026, 11, 4), contract_request=self.request,
        )
        initial = self._initial_reading()
        Reading.objects.filter(id=initial.id).update(contract=new, is_active=True)

        created = ensure_termination_close_readings(self.termination)

        self.assertEqual([reading.contract for reading in created], [self.old])
        initial.refresh_from_db()
        self.assertEqual(initial.contract, new)

    def test_links_the_existing_reading_of_the_same_day(self):
        same_day = self._reading(self.old, date(2026, 11, 4), 130)
        self._initial_reading()

        self.assertEqual(ensure_termination_close_readings(self.termination), [])
        self.assertEqual(list(self.termination.readings.all()), [same_day])

    def test_keeps_the_readings_already_linked_to_the_termination(self):
        linked = self._reading(self.old, date(2026, 11, 3), 129)
        self.termination.readings.add(linked)
        self._initial_reading()

        self.assertEqual(ensure_termination_close_readings(self.termination), [])
        self.assertEqual(list(self.termination.readings.all()), [linked])

    def test_does_nothing_with_later_readings_on_the_old_contract(self):
        self._reading(self.old, date(2026, 11, 20), 140)
        self._initial_reading()

        self.assertEqual(ensure_termination_close_readings(self.termination), [])
        self.assertFalse(self.termination.readings.exists())

    def test_skips_requests_billing_the_full_period(self):
        self.request.bill_full_period = True
        self.request.save()
        self._initial_reading()

        self.assertEqual(ensure_termination_close_readings(self.termination), [])

    def test_skips_change_of_name_keeping_the_code(self):
        self.request.is_change_of_name = True
        self.request.keep_same_code = True
        self.request.save()
        self._initial_reading()

        self.assertEqual(ensure_termination_close_readings(self.termination), [])


class TestTerminationInvoiceReadings(TerminationCloseReadingTestBase):

    def test_does_not_bill_again_a_reading_already_billed(self):
        with self.assertRaises(TerminationCloseReadingMissingError):
            invoice_contract_termination_generate(None, self.termination.id, None, None, is_budget=True)

    def test_a_prefactura_does_not_count_as_billed(self):
        Invoice.objects.filter(readings=self.billed).update(type_final='P')

        try:
            invoice_contract_termination_generate(None, self.termination.id, None, None, is_budget=True)
        except TerminationCloseReadingMissingError:
            self.fail('A reading with only a prefactura is still pending to bill')
        except Exception:
            # La resta de la generació necessita tarifes que aquí no hi són.
            pass
