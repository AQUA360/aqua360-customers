from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.db.models import Max
from django.test import TestCase
from django.utils import timezone

from billing.models import Biller, Billing, BillingStatus, InvoiceWarning, Reading
from billing.tasks import process_billing_batch
from contract.models import Contract, ContractStatus, ContractTerminationRequest, ContractTerminationStatus
from coredata.models import ConfigProject, Person
from service.models import Company, Meter, Property, Route, RoutePosition, SupplyPoint


# La tasca tanca connexions entre contractes; dins d'un TestCase trencaria la transacció.
@mock.patch('billing.tasks.close_old_connections')
@mock.patch('billing.tasks.ProgressRecorder')
class TestTerminatedContractBilling(TestCase):
    """Un contracte de baixa amb lectures anteriors a la baixa no es factura d'ofici:
    la factura neix exclosa i amb l'avís, i només s'emet si l'usuari la torna a incloure."""

    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('contract_active_token', 'ACTIVE'),
            ('contract_terminated_status', 'TERMINATED'),
            ('contract_termination_completed_token', 'COMPLETED'),
            ('billing_batch_pending', 'PENDING'),
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

    def _process(self):
        """Factures simulades (com a test_billing_process_errors): només interessa què en fa la tasca."""
        invoices = {}

        def fake_generate(contract, readings, *args, **kwargs):
            invoice = mock.MagicMock(id=900000 + contract.id, total_final=Decimal('10'), payment_type=None, is_excluded=False)
            invoices[contract.id] = invoice
            return invoice

        with mock.patch('billing.tasks.generate_consumption_invoice_multiple', side_effect=fake_generate):
            process_billing_batch(self.billing.id)
        self.billing.refresh_from_db()
        self.assertEqual(self.billing.process_errors, [])
        return invoices

    @staticmethod
    def _saved_fields(invoice):
        return [field for call in invoice.save.call_args_list for field in call.kwargs.get('update_fields', [])]

    def test_terminated_contract_invoice_is_excluded_with_warning(self, _progress, _close):
        invoice = self._process()[self.contracts['terminated'].id]

        self.assertTrue(invoice.is_excluded)
        self.assertEqual(invoice.warning, self.terminated_warning)
        self.assertIn('is_excluded', self._saved_fields(invoice))
        self.assertIn('warning', self._saved_fields(invoice))

    def test_active_contract_invoice_is_not_excluded(self, _progress, _close):
        invoice = self._process()[self.contracts['active'].id]

        self.assertFalse(invoice.is_excluded)
        self.assertNotEqual(invoice.warning, self.terminated_warning)
        self.assertNotIn('is_excluded', self._saved_fields(invoice))

    def test_terminated_contract_is_excluded_without_configured_warning(self, _progress, _close):
        ConfigProject.objects.filter(token='invoice_warning_terminated_contract').delete()

        invoice = self._process()[self.contracts['terminated'].id]

        self.assertTrue(invoice.is_excluded)
        self.assertIn('is_excluded', self._saved_fields(invoice))
