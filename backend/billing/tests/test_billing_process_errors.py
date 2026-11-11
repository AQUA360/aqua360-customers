from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from billing.models import Biller, Billing, BillingQueue, BillingStatus, InvoiceWarning, Reading
from billing.tasks import process_billing_batch
from billing.utils.billing_process_errors import (
    BillingProcessError, classify_billing_error, dedupe_contract_readings, remove_billing_process_errors,
    upsert_billing_process_error,
)
from billing.views.billing_view import BillingViewSet
from contract.models import Contract, ContractStatus
from coredata.models import ConfigProject, Person
from service.models import Company, Meter, Property, Route, RoutePosition, SupplyPoint


class TestClassifyBillingError(SimpleTestCase):
    """Els errors es tradueixen a un codi i un missatge, sense el text de l'excepció."""

    def test_wrapped_config_error_is_recognised(self):
        try:
            try:
                raise ConfigProject.DoesNotExist('ConfigProject matching query does not exist.')
            except Exception:
                raise Exception('Error creating line items')
        except Exception as exc:
            error = classify_billing_error(exc)
        self.assertEqual(error['code'], 'missing_config')

    def test_unknown_error_does_not_expose_exception_text(self):
        error = classify_billing_error(AttributeError("'NoneType' object has no attribute 'code'"))
        self.assertEqual(error['code'], 'unknown')
        self.assertNotIn('NoneType', error['message'])
        self.assertNotIn('NoneType', error['hint'])

    def test_reading_without_meter(self):
        sp = SimpleNamespace(name='PS-1', token='sp-1')
        reading = SimpleNamespace(meter_id=None, meter=None, supply_point=sp, reading_date=timezone.now().date(), calculated_value=Decimal('1'))
        contract = SimpleNamespace(token='C-1')
        with self.assertRaises(BillingProcessError) as ctx:
            dedupe_contract_readings(contract, [reading])
        self.assertEqual(ctx.exception.code, 'reading_without_meter')
        self.assertIn('PS-1', ctx.exception.message)

    def test_dedupe_keeps_first_reading_per_meter(self):
        meter = SimpleNamespace(code='M-1')
        r1 = SimpleNamespace(meter_id=1, meter=meter, supply_point=None, reading_date=timezone.now().date(), calculated_value=Decimal('1'))
        r2 = SimpleNamespace(meter_id=1, meter=meter, supply_point=None, reading_date=timezone.now().date(), calculated_value=Decimal('2'))
        self.assertEqual(dedupe_contract_readings(SimpleNamespace(token='C-1'), [r1, r2]), [r1])

    def test_discarded_reading_without_consumption_does_not_block(self):
        meter = SimpleNamespace(code='M-1')
        recent = SimpleNamespace(meter_id=1, meter=meter, supply_point=None, reading_date=timezone.now().date(), calculated_value=Decimal('1'))
        old = SimpleNamespace(meter_id=1, meter=meter, supply_point=None, reading_date=timezone.now().date(), calculated_value=None)
        self.assertEqual(dedupe_contract_readings(SimpleNamespace(token='C-1'), [recent, old]), [recent])
        with self.assertRaises(BillingProcessError) as ctx:
            dedupe_contract_readings(SimpleNamespace(token='C-1'), [old, recent])
        self.assertEqual(ctx.exception.code, 'reading_without_consumption')


class ProcessErrorsBase(TestCase):

    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('contract_active_token', 'ACTIVE'),
            ('contract_terminated_status', 'TERMINATED'),
            ('contract_termination_completed_token', 'COMPLETED'),
            ('billing_batch_pending', 'PENDING'),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})
        for token in ('negative', 'zero', 'bank_missing', 'payment_missing', 'simplified_over_400', 'high_amount'):
            # Es reaprofiten els avisos que ja carreguen les migracions de dades
            config, _ = ConfigProject.objects.get_or_create(token=f'invoice_warning_{token}', defaults={'value': f'W_{token}'})
            if not InvoiceWarning.objects.filter(token=config.value).exists():
                InvoiceWarning.objects.create(token=config.value, name=token)
        BillingStatus.objects.get_or_create(token='PENDING', defaults={'name': 'Pendent'})
        active, _ = ContractStatus.objects.get_or_create(token='ACTIVE', defaults={'name': 'Actiu'})

        company = Company.objects.create(name='Company process errors')
        holder = Person.objects.create(name='Holder', surname='Errors', token='holder-process-errors')
        cls.biller = Biller.objects.create(token='biller-process-errors', name='Biller', period_type='trimestral')
        route = Route.objects.create(token='route-process-errors', biller=cls.biller)
        position = RoutePosition.objects.create(route=route, position=1)
        prop = Property.objects.create(token='property-process-errors', route_position=position)
        cls.billing = Billing.objects.create(token='FACT-PROCESS-ERRORS', biller=cls.biller, name='Facturació')

        today = timezone.now().date()
        cls.contracts = {}
        for key in ('ok', 'no_meter', 'crash'):
            sp = SupplyPoint.objects.create(token=f'sp-process-errors-{key}', name=f'PS-{key}', property=prop)
            contract = Contract.objects.create(
                company=company, token=f'CON-PROCESS-ERRORS-{key}', status=active, is_active=True,
                holder=holder, supply_point_default=sp,
            )
            contract.supply_points.add(sp)
            meter = None if key == 'no_meter' else Meter.objects.create(code=f'M-process-errors-{key}', token=f'M-process-errors-{key}')
            Reading.objects.create(
                billing=cls.billing, contract=contract, supply_point=sp, meter=meter,
                reading_date=today, reading_value=Decimal('100'), calculated_value=Decimal('10'),
            )
            cls.contracts[key] = contract

        cls.user = get_user_model().objects.create_superuser(username='process-errors', password='x', email='')


# La tasca tanca connexions entre contractes; dins d'un TestCase trencaria la transacció.
@mock.patch('billing.tasks.close_old_connections')
@mock.patch('billing.tasks.ProgressRecorder')
class TestProcessBillingBatchErrors(ProcessErrorsBase):
    """Si un contracte falla, el lot continua i l'error queda a la facturació."""

    def test_failing_contracts_are_recorded_and_the_rest_processed(self, _progress, _close):
        calls = []
        # Un error desat per un altre procés mentre el lot treballa no s'ha de perdre
        concurrent = {'contract_id': 999999, 'code': 'unknown'}

        def fake_generate(contract, readings, *args, **kwargs):
            calls.append(contract.id)
            if contract.id == self.contracts['crash'].id:
                raise AttributeError("'NoneType' object has no attribute 'code'")
            upsert_billing_process_error(self.billing.id, concurrent)
            return mock.MagicMock(id=999999, total_final=Decimal('10'), payment_type=None)

        with mock.patch('billing.tasks.generate_consumption_invoice_multiple', side_effect=fake_generate):
            process_billing_batch(self.billing.id)

        self.assertCountEqual(calls, [self.contracts['ok'].id, self.contracts['crash'].id])
        self.billing.refresh_from_db()
        errors = {e['contract_id']: e for e in self.billing.process_errors}
        self.assertEqual(set(errors), {self.contracts['no_meter'].id, self.contracts['crash'].id, 999999})
        self.assertEqual(errors[self.contracts['no_meter'].id]['code'], 'reading_without_meter')
        self.assertEqual(errors[self.contracts['no_meter'].id]['contract_token'], 'CON-PROCESS-ERRORS-no_meter')
        self.assertEqual(errors[self.contracts['crash'].id]['code'], 'unknown')
        self.assertEqual(self.billing.status.token, 'PENDING')

    def test_contract_without_generated_invoice_is_recorded(self, _progress, _close):
        with mock.patch('billing.tasks.generate_consumption_invoice_multiple', return_value=None):
            process_billing_batch(self.billing.id)

        self.billing.refresh_from_db()
        errors = {e['contract_id']: e['code'] for e in self.billing.process_errors}
        self.assertEqual(errors[self.contracts['ok'].id], 'no_invoice_generated')

    def test_global_error_closes_queue_item_with_readable_message(self, _progress, _close):
        billing = Billing.objects.create(token='FACT-NO-BILLER')
        item = BillingQueue.objects.create(billing=billing, task_type='PRE_INVOICE', status='running')

        with self.assertRaises(Exception) as ctx:
            process_billing_batch(billing.id, queue_item_id=item.id)

        item.refresh_from_db()
        self.assertEqual(item.status, 'failed')
        self.assertIn('facturador', item.error_message)
        self.assertNotIn('has no biller', item.error_message)
        self.assertNotIn('has no biller', str(ctx.exception))


class TestProcessContractEndpoint(ProcessErrorsBase):
    """Corregit el contracte, es torna a processar i l'error desapareix."""

    def _post(self, action, data):
        request = APIRequestFactory().post(f'/billing/billing/{self.billing.id}/{action}/', data, format='json')
        force_authenticate(request, user=self.user)
        name = action.replace('-', '_')
        return BillingViewSet.as_view({'post': name})(request, pk=self.billing.id)

    def test_retry_records_error_then_clears_it_once_fixed(self):
        contract = self.contracts['no_meter']
        response = self._post('process-contract', {'contract_id': contract.id})
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data['code'], 'reading_without_meter')
        self.billing.refresh_from_db()
        self.assertEqual([e['contract_id'] for e in self.billing.process_errors], [contract.id])

        meter = Meter.objects.create(code='M-fixed', token='M-fixed')
        Reading.objects.filter(contract=contract).update(meter=meter)
        invoice = mock.MagicMock(id=1, total_final=Decimal('10'), payment_type=None)
        with mock.patch('billing.utils.invoice_service.generate_consumption_invoice_multiple', return_value=invoice):
            response = self._post('process-contract', {'contract_id': contract.id})

        self.assertEqual(response.status_code, 200, response.data)
        self.billing.refresh_from_db()
        self.assertEqual(self.billing.process_errors, [])

    def test_dismiss_removes_error(self):
        upsert_billing_process_error(self.billing.id, {'contract_id': self.contracts['crash'].id, 'code': 'unknown'})
        upsert_billing_process_error(self.billing.id, {'contract_id': self.contracts['ok'].id, 'code': 'unknown'})

        response = self._post('dismiss-process-errors', {'contract_ids': [self.contracts['crash'].id]})

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([e['contract_id'] for e in response.data], [self.contracts['ok'].id])

    def test_upsert_replaces_previous_error_of_same_contract(self):
        cid = self.contracts['crash'].id
        upsert_billing_process_error(self.billing.id, {'contract_id': cid, 'code': 'unknown'})
        upsert_billing_process_error(self.billing.id, {'contract_id': cid, 'code': 'missing_config'})
        self.billing.refresh_from_db()
        self.assertEqual(self.billing.process_errors, [{'contract_id': cid, 'code': 'missing_config'}])
        self.assertTrue(remove_billing_process_errors(self.billing.id, [cid]))
        self.assertFalse(remove_billing_process_errors(self.billing.id, [cid]))
