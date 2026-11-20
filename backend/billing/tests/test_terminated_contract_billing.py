from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.db.models import Max
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from billing.models import Biller, Billing, BillingQueue, BillingStatus, InvoiceWarning, Reading
from billing.tasks import process_billing_batch
from billing.utils.terminated_contract_billing import (
    TerminatedContractSelectionError, resolve_terminated_contract_selection, terminated_billable_contracts,
)
from billing.views.billing_batch_generate_view import BillingBatchSummaryView
from billing.views.billing_batch_regenerate_view import BillingBatchRegenerateView
from billing.views.billing_terminated_contracts_view import BillingTerminatedContractsView
from contract.models import Contract, ContractStatus, ContractTerminationRequest, ContractTerminationStatus
from coredata.models import ConfigProject, Person
from service.models import Company, Meter, Property, Route, RoutePosition, SupplyPoint


class TerminatedContractBillingBase(TestCase):
    """Facturació amb un contracte actiu i un de baixa amb la lectura anterior a la baixa."""

    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('contract_active_token', 'ACTIVE'),
            ('contract_terminated_status', 'TERMINATED'),
            ('contract_termination_completed_token', 'COMPLETED'),
            ('billing_batch_pending', 'PENDING'),
            ('billing_batch_processing', 'PROCESSING'),
            ('invoice_status_pending_token', 'INV_PENDING'),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})
        for token in ('negative', 'zero', 'bank_missing', 'payment_missing', 'simplified_over_400',
                      'high_amount', 'terminated_contract'):
            # Es reaprofiten els avisos que ja carreguen les migracions de dades
            config, _ = ConfigProject.objects.get_or_create(token=f'invoice_warning_{token}', defaults={'value': f'W_{token}'})
            if not InvoiceWarning.objects.filter(token=config.value).exists():
                # Id explícit: la seqüència pot no estar al dia amb les files de les migracions
                next_id = (InvoiceWarning.objects.aggregate(m=Max('id'))['m'] or 0) + 1
                InvoiceWarning.objects.create(id=next_id, token=config.value, name=token)
        cls.terminated_warning = InvoiceWarning.objects.get(
            token=ConfigProject.objects.get(token='invoice_warning_terminated_contract').value,
        )
        BillingStatus.objects.get_or_create(token='PENDING', defaults={'name': 'Pendent'})
        BillingStatus.objects.get_or_create(token='PROCESSING', defaults={'name': 'Processant'})
        active, _ = ContractStatus.objects.get_or_create(token='ACTIVE', defaults={'name': 'Alta'})
        terminated, _ = ContractStatus.objects.get_or_create(token='TERMINATED', defaults={'name': 'Baixa'})
        completed, _ = ContractTerminationStatus.objects.get_or_create(token='COMPLETED', defaults={'name': 'Finalitzada'})

        company = Company.objects.create(name='Company terminated billing')
        holder = Person.objects.create(name='Holder', surname='Terminated', token='holder-terminated-billing')
        biller = Biller.objects.create(token='biller-terminated-billing', name='Biller', period_type='trimestral')
        route = Route.objects.create(token='route-terminated-billing', biller=biller)
        position = RoutePosition.objects.create(route=route, position=1)
        prop = Property.objects.create(token='property-terminated-billing', route_position=position)
        cls.billing = Billing.objects.create(token='FACT-TERMINATED', biller=biller, name='Facturació')

        reading_date = timezone.now().date() - timedelta(days=30)
        cls.contracts = {}
        for key, status in (('active', active), ('terminated', terminated)):
            sp = SupplyPoint.objects.create(token=f'sp-terminated-billing-{key}', name=f'PS-{key}', property=prop)
            contract = Contract.objects.create(
                company=company, token=f'CON-TERMINATED-BILLING-{key}', status=status, is_active=True,
                holder=holder, supply_point_default=sp,
            )
            contract.supply_points.add(sp)
            meter = Meter.objects.create(code=f'M-terminated-billing-{key}', token=f'M-terminated-billing-{key}')
            Reading.objects.create(
                billing=cls.billing, contract=contract, supply_point=sp, meter=meter,
                reading_date=reading_date, reading_value=Decimal('100'), calculated_value=Decimal('10'),
            )
            cls.contracts[key] = contract

        # Baixa finalitzada després de la lectura del lot: la lectura entra a la facturació.
        # Amb update(): el senyal de la baixa necessita tota la configuració d'ordres.
        termination = ContractTerminationRequest.objects.create(contract=cls.contracts['terminated'])
        ContractTerminationRequest.objects.filter(id=termination.id).update(
            status=completed, approved_at=timezone.now() - timedelta(days=10),
        )
        cls.user = get_user_model().objects.create_superuser(username='terminated-billing', password='x', email='')


# La tasca tanca connexions entre contractes; dins d'un TestCase trencaria la transacció.
@mock.patch('billing.tasks.close_old_connections')
@mock.patch('billing.tasks.ProgressRecorder')
class TestTerminatedContractBillingTask(TerminatedContractBillingBase):
    """Un contracte de baixa només es factura si l'usuari l'ha triat."""

    def _process(self, queue_item=None):
        """Factures simulades (com a test_billing_process_errors): només interessa què en fa la tasca."""
        invoices = {}

        def fake_generate(contract, readings, *args, **kwargs):
            invoice = mock.MagicMock(id=900000 + contract.id, total_final=Decimal('10'), payment_type=None)
            invoices[contract.id] = invoice
            return invoice

        with mock.patch('billing.tasks.generate_consumption_invoice_multiple', side_effect=fake_generate):
            process_billing_batch(self.billing.id, queue_item_id=queue_item.id if queue_item else None)
        self.billing.refresh_from_db()
        self.assertEqual(self.billing.process_errors, [])
        return invoices

    def test_terminated_contract_not_selected_is_not_billed(self, _progress, _close):
        invoices = self._process()

        self.assertNotIn(self.contracts['terminated'].id, invoices)
        self.assertIn(self.contracts['active'].id, invoices)

    def _queue_item(self, ids):
        return BillingQueue.objects.create(
            billing=self.billing, task_type='PRE_INVOICE', status='running',
            payload={'terminated_contract_ids': ids},
        )

    def test_selected_terminated_contract_is_billed_with_warning(self, _progress, _close):
        item = self._queue_item([self.contracts['terminated'].id])

        invoice = self._process(item)[self.contracts['terminated'].id]

        self.assertEqual(invoice.warning, self.terminated_warning)
        # No s'exclou: l'usuari ja ha decidit facturar-la
        invoice.save.assert_called_with(update_fields=['warning'])

    def test_later_confirmation_does_not_change_queued_selection(self, _progress, _close):
        """Cada element de la cua factura amb la tria de la seva confirmació."""
        first = self._queue_item([self.contracts['terminated'].id])
        self._queue_item([])

        invoices = self._process(first)

        self.assertIn(self.contracts['terminated'].id, invoices)

    def test_active_contract_has_no_terminated_warning(self, _progress, _close):
        invoice = self._process()[self.contracts['active'].id]

        self.assertNotEqual(invoice.warning, self.terminated_warning)


class TestTerminatedContractSelection(TerminatedContractBillingBase):

    def test_candidates_are_the_terminated_contracts_with_readings(self):
        ids = list(terminated_billable_contracts(self.billing).values_list('id', flat=True))
        self.assertEqual(ids, [self.contracts['terminated'].id])

    def test_empty_selection_bills_none(self):
        self.assertEqual(resolve_terminated_contract_selection(self.billing, None), [])
        self.assertEqual(resolve_terminated_contract_selection(self.billing, []), [])

    def test_selection_accepts_candidates(self):
        cid = self.contracts['terminated'].id
        self.assertEqual(resolve_terminated_contract_selection(self.billing, [str(cid)]), [cid])

    def test_selection_rejects_contracts_outside_the_billing(self):
        cid = self.contracts['terminated'].id
        for raw in ([self.contracts['active'].id], [999999], ['x'], [True], 'abc', [cid + 0.9], [float(cid)], [f'{cid}.9']):
            with self.assertRaises(TerminatedContractSelectionError, msg=raw):
                resolve_terminated_contract_selection(self.billing, raw)


class TestTerminatedContractEndpoints(TerminatedContractBillingBase):
    factory = APIRequestFactory()

    def test_list_returns_terminated_contracts(self):
        request = self.factory.get(f'/billing/billing/{self.billing.id}/terminated-contracts')
        force_authenticate(request, user=self.user)
        response = BillingTerminatedContractsView.as_view()(request, id=self.billing.id)

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([c['id'] for c in response.data['results']], [self.contracts['terminated'].id])

    def _post_summary(self, data):
        request = self.factory.post('/billing/billing-batch/summary', data, format='json')
        force_authenticate(request, user=self.user)
        return BillingBatchSummaryView.as_view()(request)

    def test_process_rejects_invalid_selection_without_queueing(self):
        with mock.patch('billing.views.billing_batch_generate_view.process_next_queue_item') as queue:
            response = self._post_summary({'billing': self.billing.id, 'terminated_contract_ids': [999999]})

        self.assertEqual(response.status_code, 400)
        queue.assert_not_called()
        self.assertFalse(BillingQueue.objects.filter(billing=self.billing).exists())

    def test_process_saves_selection_on_queue_item(self):
        cid = self.contracts['terminated'].id

        with mock.patch('billing.views.billing_batch_generate_view.process_next_queue_item'):
            response = self._post_summary({'billing': self.billing.id, 'terminated_contract_ids': [cid]})

        self.assertEqual(response.status_code, 202, response.data)
        item = BillingQueue.objects.get(id=response.data['queue_item_id'])
        self.assertEqual(item.payload, {'terminated_contract_ids': [cid]})

    def test_recalculate_rejects_invalid_selection_before_deleting(self):
        request = self.factory.post(
            f'/billing/billing/{self.billing.id}/recalculate', {'terminated_contract_ids': [999999]}, format='json',
        )
        force_authenticate(request, user=self.user)
        with mock.patch('billing.tasks.process_next_queue_item') as queue:
            response = BillingBatchRegenerateView.as_view()(request, id=self.billing.id)

        self.assertEqual(response.status_code, 400)
        queue.assert_not_called()
