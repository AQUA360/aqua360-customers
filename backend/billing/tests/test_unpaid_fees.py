from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient

from billing.filter.invoice_filter import InvoiceFilter
from billing.models import Invoice, InvoiceLineItem, InvoiceStatus, Payment, PaymentStatus, UnpaidFeeRun
from billing.tasks import generate_unpaid_fee_invoices_task
from billing.utils.unpaid_fee_service import generate_unpaid_fee_invoices
from contract.models import Contract, ContractRequest
from coredata.models import ConfigProject, Person
from pricing.models import PriceRate, ProductOrigin


class UnpaidFeeTestMixin:
    def setUp(self):
        for token, value in (
            ('invoice_status_expired_token', 'EXPIRED'),
            ('invoice_status_paid_token', 'PAID'),
            ('invoice_status_cancelled_token', 'CANCELLED'),
            ('payment_status_returned_token', 'RETURNED'),
            ('invoice_return_price_rate_token', 'DESP_IMP'),
            ('origin_reading_token', 'READING'),
            ('origin_contract_token', 'CONTRACT'),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})
        self.expired = InvoiceStatus.objects.create(token='EXPIRED', name='Vençuda')
        self.confirmed = InvoiceStatus.objects.create(token='CONFIRMED', name='Confirmada')
        self.cancelled = InvoiceStatus.objects.create(token='CANCELLED', name='Anul·lada')
        self.returned = PaymentStatus.objects.create(token='RETURNED', name='Retornat')
        self.fee_rate = PriceRate.objects.create(token='DESP_IMP', name='Despeses impagament', is_return_fee=True)
        self.other_rate = PriceRate.objects.create(token='ALTRES', name='Altres despeses')
        self.reading = ProductOrigin.objects.create(token='READING', name='Lectura')
        # Sense senyals: els del contracte demanen configuració que aquí no cal.
        self.contract = Contract.objects.bulk_create([Contract(token='C0')])[0]

    def invoice(self, token, status=None, left_to_pay=10, payment_type='BANK_PAYMENT', **kwargs):
        kwargs.setdefault('origin', self.reading)
        if 'contract_request' not in kwargs:
            kwargs.setdefault('contract', self.contract)
        return Invoice.objects.create(
            token=token, status=status or self.expired, left_to_pay=left_to_pay,
            payment_type_token_final=payment_type, **kwargs,
        )

    def add_fee(self, parent, token, price_rate=None, status=None):
        fee = Invoice.objects.create(token=token, status=self.confirmed, left_to_pay=0.54, parent_invoice=parent)
        InvoiceLineItem.objects.create(invoice=fee, price_rate=price_rate or self.fee_rate, name='Despeses')
        if status:
            # Sense senyals: el d'anul·lació arrossega tota la cadena.
            Invoice.objects.filter(id=fee.id).update(status=status)
        return fee

    def returned_payment(self, invoice):
        # Sense senyals: el de pagament arrossega l'estat de la factura.
        Payment.objects.bulk_create([Payment(token=f'P-{invoice.token}', invoice=invoice, status=self.returned)])


class UnpaidFeeFilterTests(UnpaidFeeTestMixin, TestCase):

    def filtered(self, **params):
        return sorted(InvoiceFilter(params, queryset=Invoice.objects.all()).qs.values_list('token', flat=True))

    def test_unpaid_status_selects_expired_and_returned_with_debt(self):
        self.invoice('VENCUDA')
        self.invoice('PAGADA', left_to_pay=0)
        returned = self.invoice('RETORNADA', status=self.confirmed, payment_type='DIRECT_DEBIT')
        self.returned_payment(returned)
        self.invoice('CONFIRMADA', status=self.confirmed)

        self.assertEqual(self.filtered(unpaid_status='expired'), ['VENCUDA'])
        self.assertEqual(self.filtered(unpaid_status='returned'), ['RETORNADA'])
        self.assertEqual(self.filtered(unpaid_status='expired,returned'), ['RETORNADA', 'VENCUDA'])
        self.assertEqual(
            self.filtered(unpaid_status='expired,returned', payment_type_tokens='BANK_PAYMENT'), ['VENCUDA'])

    def test_without_fee_drops_fee_invoices_and_invoices_that_already_have_one(self):
        self.invoice('SENSE')
        managed = self.invoice('AMB')
        # La despesa penja de l'última filla de la cadena.
        child = self.invoice('FILLA', parent_invoice=managed)
        fee = self.add_fee(child, 'DESPESA')
        fee.status = self.expired
        fee.save()

        tokens = self.filtered(unpaid_status='expired', without_fee_price_rates=str(self.fee_rate.id))

        self.assertEqual(tokens, ['SENSE'])

    def test_exclude_vulnerable(self):
        vulnerable = Person.objects.create(name='A', vulnerability_level=2)
        other = Person.objects.create(name='B', vulnerability_level=0)
        # Sense senyals: els del contracte demanen configuració que aquí no cal.
        vulnerable_contract, other_contract = Contract.objects.bulk_create([
            Contract(token='C1', holder=vulnerable), Contract(token='C2', holder=other)])
        self.invoice('VULNERABLE', contract=vulnerable_contract)
        self.invoice('NORMAL', contract=other_contract)

        self.assertEqual(self.filtered(unpaid_status='expired'), ['NORMAL', 'VULNERABLE'])
        self.assertEqual(self.filtered(unpaid_status='expired', exclude_vulnerable='true'), ['NORMAL'])

    def test_exclude_vulnerable_checks_the_contract_request_without_contract(self):
        vulnerable = Person.objects.create(name='A', vulnerability_level=2)
        request = ContractRequest.objects.bulk_create([ContractRequest(holder=vulnerable)])[0]
        self.invoice('ALTA', contract_request=request)
        self.invoice('NORMAL')

        self.assertEqual(self.filtered(unpaid_status='expired', exclude_vulnerable='true'), ['NORMAL'])

    def test_only_reading_and_contract_origins_are_eligible(self):
        connection = ProductOrigin.objects.create(token='CONNECTION', name='Escomesa')
        self.invoice('LECTURA')
        self.invoice('ESCOMESA', origin=connection)
        self.invoice('SENSE_CONTRACTE', contract=None)

        self.assertEqual(self.filtered(unpaid_status='expired'), ['LECTURA'])

    def test_cancelled_fees_do_not_count(self):
        invoice = self.invoice('ANULLADA')
        self.add_fee(invoice, 'DESPESA', status=self.cancelled)

        self.assertEqual(
            self.filtered(unpaid_status='expired', without_fee_price_rates=str(self.fee_rate.id)), ['ANULLADA'])

    def test_invoice_stays_while_a_selected_fee_is_missing(self):
        invoice = self.invoice('AMB_UNA')
        self.add_fee(invoice, 'DESPESA')
        both = f'{self.fee_rate.id},{self.other_rate.id}'

        self.assertEqual(self.filtered(unpaid_status='expired', without_fee_price_rates=both), ['AMB_UNA'])
        self.assertEqual(
            self.filtered(unpaid_status='expired', without_fee_price_rates=str(self.fee_rate.id)), [])


class GenerateUnpaidFeeTests(UnpaidFeeTestMixin, TestCase):

    def test_creates_one_fee_per_root_invoice_and_skips_managed_ones(self):
        root = self.invoice('ARREL')
        child = self.invoice('FILLA', parent_invoice=root)
        managed = self.invoice('GESTIONADA')
        self.add_fee(managed, 'DESPESA')
        failing = self.invoice('ERROR')

        def fake_charge(invoice, title, fee_price_rates=None):
            if invoice.id == failing.id:
                # El que s'hagi desat abans de l'error es desfà.
                Invoice.objects.create(token='A_MITGES')
                raise Exception('boom')
            self.assertEqual(fee_price_rates, [self.fee_rate])
            return self.add_fee(invoice, f'D-{invoice.token}')

        with patch('billing.utils.invoice_service.invoice_return_charge', side_effect=fake_charge) as charge:
            result = generate_unpaid_fee_invoices(
                [root.id, child.id, managed.id, failing.id], [self.fee_rate.id])

        self.assertEqual([call.args[0].token for call in charge.call_args_list], ['ARREL', 'ERROR'])
        self.assertEqual(result['created'], 1)
        self.assertEqual(result['skipped'], 2)
        self.assertEqual(result['errors'], [{'invoice': 'ERROR', 'error': 'Error creating the fee invoice'}])
        self.assertFalse(Invoice.objects.filter(token='A_MITGES').exists())

    def test_applies_only_the_missing_fees(self):
        invoice = self.invoice('AMB_UNA')
        self.add_fee(invoice, 'DESPESA')

        with patch('billing.utils.invoice_service.invoice_return_charge') as charge:
            generate_unpaid_fee_invoices([invoice.id], [self.fee_rate.id, self.other_rate.id])

        self.assertEqual(charge.call_args.kwargs['fee_price_rates'], [self.other_rate])

    def test_skips_excluded_roots_and_invoices_paid_meanwhile(self):
        root = self.invoice('ARREL_EXCLOSA')
        child = self.invoice('FILLA', parent_invoice=root)
        paid = self.invoice('PAGADA', left_to_pay=0)

        with patch('billing.utils.invoice_service.invoice_return_charge') as charge:
            result = generate_unpaid_fee_invoices(
                [child.id, paid.id], [self.fee_rate.id], excluded_ids=[root.id])

        charge.assert_not_called()
        self.assertEqual(result['skipped'], 2)


class UnpaidFeeEndpointTests(UnpaidFeeTestMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('operador')
        self.user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='billing', codename__in=['view_invoice', 'add_invoice']))
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def enable(self, value):
        ConfigProject.objects.update_or_create(token='unpaid_fee_operation_enabled', defaults={'value': value})

    def test_config_reports_default_fee(self):
        self.enable('true')
        response = self.client.get('/billing/invoice/unpaid-fees/config/')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['enabled'])
        self.assertEqual([r['token'] for r in response.data['default_price_rates']], ['DESP_IMP'])

    def test_generate_is_forbidden_when_disabled(self):
        self.enable('false')
        response = self.client.post(
            '/billing/invoice/unpaid-fees/generate/?unpaid_status=expired',
            {'price_rate_ids': [self.fee_rate.id]}, format='json')

        self.assertEqual(response.status_code, 403)

    def test_generate_launches_task_with_filtered_invoices_minus_excluded(self):
        self.enable('true')
        kept = self.invoice('A')
        excluded = self.invoice('B')
        self.invoice('C', status=self.confirmed)

        with patch('billing.tasks.generate_unpaid_fee_invoices_task.delay') as delay:
            delay.return_value.id = 'task-1'
            response = self.client.post(
                '/billing/invoice/unpaid-fees/generate/?unpaid_status=expired',
                {'price_rate_ids': [self.fee_rate.id], 'excluded_ids': [excluded.id]}, format='json')

        self.assertEqual(response.status_code, 202)
        run = UnpaidFeeRun.objects.get()
        delay.assert_called_once_with([kept.id], [self.fee_rate.id], run_id=run.id, excluded_ids=[excluded.id])
        self.assertEqual((run.task_id, run.invoice_count, run.created_by), ('task-1', 1, self.user))
        self.assertEqual(list(run.price_rates.all()), [self.fee_rate])

    def test_generate_always_requires_unpaid_invoices(self):
        self.enable('true')
        pending = self.invoice('PENDENT')
        self.invoice('PAGADA', left_to_pay=0)
        self.invoice('CONFIRMADA', status=self.confirmed)

        with patch('billing.tasks.generate_unpaid_fee_invoices_task.delay') as delay:
            delay.return_value.id = 'task-1'
            response = self.client.post(
                '/billing/invoice/unpaid-fees/generate/', {'price_rate_ids': [self.fee_rate.id]}, format='json')

        self.assertEqual(response.status_code, 202)
        self.assertEqual(delay.call_args.args[0], [pending.id])

    def test_generate_rejects_unknown_fees(self):
        self.enable('true')
        self.invoice('A')
        response = self.client.post(
            '/billing/invoice/unpaid-fees/generate/?unpaid_status=expired',
            {'price_rate_ids': [self.fee_rate.id, 999999]}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(UnpaidFeeRun.objects.exists())

    def test_generate_releases_the_run_if_the_task_cannot_be_queued(self):
        self.enable('true')
        self.invoice('A')
        with patch('billing.tasks.generate_unpaid_fee_invoices_task.delay', side_effect=Exception('broker')):
            response = self.client.post(
                '/billing/invoice/unpaid-fees/generate/?unpaid_status=expired',
                {'price_rate_ids': [self.fee_rate.id]}, format='json')

        self.assertEqual(response.status_code, 503)
        self.assertEqual(UnpaidFeeRun.objects.get().status, UnpaidFeeRun.STATUS_FAILED)

    def test_only_one_run_can_be_running(self):
        UnpaidFeeRun.objects.create()
        with self.assertRaises(IntegrityError):
            UnpaidFeeRun.objects.create()

    def test_running_process_is_reported_and_blocks_another_one(self):
        self.enable('true')
        self.invoice('A')
        run = UnpaidFeeRun.objects.create(task_id='task-1', invoice_count=3, created_by=self.user)

        with patch('celery.result.AsyncResult') as async_result:
            async_result.return_value.state = 'PROGRESS'
            config = self.client.get('/billing/invoice/unpaid-fees/config/')
            with patch('billing.tasks.generate_unpaid_fee_invoices_task.delay') as delay:
                response = self.client.post(
                    '/billing/invoice/unpaid-fees/generate/?unpaid_status=expired',
                    {'price_rate_ids': [self.fee_rate.id]}, format='json')

        self.assertEqual(config.data['running_run']['task_id'], 'task-1')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['running_run']['id'], run.id)
        delay.assert_not_called()

    def test_failed_task_releases_the_process(self):
        self.enable('true')
        run = UnpaidFeeRun.objects.create(task_id='task-1')

        with patch('celery.result.AsyncResult') as async_result:
            async_result.return_value.state = 'FAILURE'
            config = self.client.get('/billing/invoice/unpaid-fees/config/')

        self.assertIsNone(config.data['running_run'])
        run.refresh_from_db()
        self.assertEqual(run.status, UnpaidFeeRun.STATUS_FAILED)
        self.assertEqual(config.data['last_run']['id'], run.id)


class UnpaidFeeTaskTests(UnpaidFeeTestMixin, TestCase):

    def test_task_saves_the_result_in_the_run(self):
        run = UnpaidFeeRun.objects.create()
        result = {'created': 2, 'created_ids': [1, 2], 'skipped': 0, 'errors': []}
        with patch('billing.utils.unpaid_fee_service.generate_unpaid_fee_invoices', return_value=dict(result)):
            generate_unpaid_fee_invoices_task.apply(args=([1, 2], [self.fee_rate.id]), kwargs={'run_id': run.id})

        run.refresh_from_db()
        self.assertEqual(run.status, UnpaidFeeRun.STATUS_DONE)
        self.assertEqual(run.result['created'], 2)
        self.assertIsNotNone(run.finished_at)

    def test_task_error_marks_the_run_as_failed(self):
        run = UnpaidFeeRun.objects.create()
        with patch('billing.utils.unpaid_fee_service.generate_unpaid_fee_invoices', side_effect=ValueError('boom')):
            generate_unpaid_fee_invoices_task.apply(args=([1], [self.fee_rate.id]), kwargs={'run_id': run.id})

        run.refresh_from_db()
        self.assertEqual((run.status, run.result), (UnpaidFeeRun.STATUS_FAILED, {'error': 'Process failed'}))

    def test_task_does_nothing_if_the_run_was_closed(self):
        run = UnpaidFeeRun.objects.create(status=UnpaidFeeRun.STATUS_FAILED)
        with patch('billing.utils.unpaid_fee_service.generate_unpaid_fee_invoices') as generate:
            generate_unpaid_fee_invoices_task.apply(args=([1], [self.fee_rate.id]), kwargs={'run_id': run.id})

        generate.assert_not_called()
