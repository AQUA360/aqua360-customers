from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase

from billing.models import Invoice, InvoiceStatus, InvoiceType
from billing.utils.payment_service import disconnect_payment_signals, reconnect_payment_signals
from billing.utils.invoice_service import apply_holder_to_budget, pass_budget_to_invoice
from billing.views.generate_invoice_budget_view import GenerateInvoiceBudgetView
from coredata.models import Address, ConfigProject, Person, PersonAddress, PersonContact


VIEW = 'billing.views.generate_invoice_budget_view'


class BudgetHolderFixturesMixin:
    def setUp(self):
        disconnect_payment_signals()
        self.addCleanup(reconnect_payment_signals)
        self.budget_type = InvoiceType.objects.create(token='tbudget', name='Pressupost')
        self.invoice_type = InvoiceType.objects.create(token='tinvoice', name='Factura')
        self.confirmed = InvoiceStatus.objects.create(token='test-confirmed', name='Confirmada')
        for token, value in (
            ('invoice_type_budget_token', 'tbudget'),
            ('invoice_type_invoice_token', 'tinvoice'),
            ('invoice_status_confirmed_token', 'test-confirmed'),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})

        self.old_holder = Person.objects.create(name='Old', surname='Holder', token='OLD-TOKEN')
        self.new_holder = Person.objects.create(name='New', surname='Holder', token='NEW-TOKEN', is_juridic=True)
        address = Address.objects.create(postal_code='00000')
        PersonAddress.objects.create(person=self.new_holder, address=address, is_billing=True)
        PersonContact.objects.create(person=self.new_holder, phone='000000000', email='holder@example.test', is_default=True)

    def make_budget(self, **overrides):
        data = {
            'token': 'BUDGET-TEST',
            'number': 'BUDGET-TEST',
            'type': self.budget_type,
            'type_final': self.budget_type.token,
            'person': self.old_holder,
            'customer_final': 'Old Holder',
            'customer_token_final': 'OLD-TOKEN',
            'payer_final': 'Old Holder',
            'payer_token_final': 'OLD-TOKEN',
            'customer_email_final': 'old@example.test',
            'address_final': 'Old address',
            'postal_code_final': '11111',
        }
        data.update(overrides)
        return Invoice.objects.create(**data)


class ApplyHolderToBudgetTest(BudgetHolderFixturesMixin, TestCase):
    def test_refreshes_customer_snapshot_from_new_holder(self):
        budget = apply_holder_to_budget(self.make_budget(), self.new_holder)
        budget.refresh_from_db()

        self.assertEqual(budget.person, self.new_holder)
        self.assertEqual(budget.customer_final, 'New Holder')
        self.assertEqual(budget.customer_token_final, 'NEW-TOKEN')
        self.assertTrue(budget.customer_is_juridic)
        self.assertEqual(budget.customer_email_final, 'holder@example.test')
        self.assertEqual(budget.customer_tlf_final, '000000000')
        self.assertEqual(budget.postal_code_final, '00000')
        self.assertEqual(budget.payer_final, 'New Holder')
        self.assertEqual(budget.payer_token_final, 'NEW-TOKEN')

    def test_keeps_bank_payer_and_address_when_holder_has_none(self):
        holder = Person.objects.create(name='Plain', token='PLAIN-TOKEN')
        budget = self.make_budget(payer_final='Bank owner', payer_token_final='BANK-TOKEN')

        apply_holder_to_budget(budget, holder)
        budget.refresh_from_db()

        self.assertEqual(budget.customer_final, 'Plain')
        self.assertEqual(budget.payer_token_final, 'BANK-TOKEN')
        self.assertEqual(budget.address_final, 'Old address')
        self.assertIsNone(budget.customer_email_final)

    def test_rejects_documents_that_are_not_budgets(self):
        invoice = self.make_budget(type=self.invoice_type, type_final=self.invoice_type.token)

        with self.assertRaises(ValueError):
            apply_holder_to_budget(invoice, self.new_holder)
        invoice.refresh_from_db()
        self.assertEqual(invoice.person, self.old_holder)

    def test_confirmed_invoice_inherits_changed_holder(self):
        budget = apply_holder_to_budget(self.make_budget(), self.new_holder)

        with patch('billing.utils.invoice_service.confirm_invoice'):
            invoice = pass_budget_to_invoice(budget)

        self.assertEqual(invoice.type, self.invoice_type)
        self.assertEqual(invoice.person, self.new_holder)
        self.assertEqual(invoice.customer_token_final, 'NEW-TOKEN')
        self.assertEqual(invoice.customer_final, 'New Holder')


class GenerateInvoiceBudgetHolderViewTest(TestCase):
    def post(self, data, holder=None, **patches):
        """Crida la vista amb les dependències de BD substituïdes per mocks."""
        with ExitStack() as stack:
            mocks = {}
            stack.enter_context(patch(f'{VIEW}.ConfigProject.objects.get'))
            stack.enter_context(patch(f'{VIEW}.disconnect_payment_signals'))
            stack.enter_context(patch(f'{VIEW}.reconnect_payment_signals'))
            serializer = stack.enter_context(patch(f'{VIEW}.InvoiceFullSerializer'))
            serializer.return_value.data = {'id': 1}
            people = stack.enter_context(patch(f'{VIEW}.Person.objects'))
            people.filter.return_value.first.return_value = holder
            people.get.return_value = MagicMock(id=99)
            mocks['apply'] = stack.enter_context(patch(f'{VIEW}.apply_holder_to_budget'))
            for name, target in patches.items():
                mocks[name] = stack.enter_context(patch(f'{VIEW}.{target}'))
            response = GenerateInvoiceBudgetView().post(SimpleNamespace(data=data, user=SimpleNamespace(id=1)))
        return response, mocks

    def test_holder_cannot_change_when_confirming_budget(self):
        response, mocks = self.post(
            {'entity': 'invoice', 'object_id': 1, 'is_budget': False, 'holder_id': 5},
            holder=MagicMock(id=5), pass_budget='pass_budget_to_invoice',
        )

        self.assertEqual(response.status_code, 400)
        mocks['pass_budget'].assert_not_called()

    def test_rebilling_holder_is_ignored_when_confirming_budget(self):
        response, mocks = self.post(
            {'entity': 'invoice', 'object_id': 1, 'is_budget': False,
             'redo_option': {'reason': 'holder', 'new_holder': 5}},
            pass_budget='pass_budget_to_invoice', invoices='Invoice.objects',
        )

        self.assertEqual(response.status_code, 200)
        mocks['pass_budget'].assert_called_once()
        mocks['apply'].assert_not_called()

    def test_unknown_holder_is_rejected(self):
        response, mocks = self.post(
            {'entity': 'custom', 'is_budget': True, 'holder_id': 404,
             'selected_custom': {'entity': 'person', 'id': 1}},
            holder=None, generate='generate_empty_invoice',
        )

        self.assertEqual(response.status_code, 400)
        mocks['generate'].assert_not_called()

    def test_custom_budget_for_contract_applies_selected_holder(self):
        holder = MagicMock(id=5)
        response, mocks = self.post(
            {'entity': 'custom', 'is_budget': True, 'holder_id': 5,
             'selected_custom': {'entity': 'contract', 'id': 1, 'type': 'custom'}},
            holder=holder, generate='generate_empty_invoice', contracts='Contract.objects',
            exploitations='Exploitation.objects',
        )

        self.assertEqual(response.status_code, 200)
        mocks['apply'].assert_called_once_with(mocks['generate'].return_value, holder)

    def test_every_budget_origin_applies_selected_holder(self):
        cases = {
            'connection_request': {'generate': 'generate_empty_invoice', 'requests': 'ConnectionRequest.objects'},
            'contract_termination_request': {
                'generate': 'invoice_contract_termination_generate',
                'terminations': 'ContractTerminationRequest.objects',
                'invoices': 'Invoice.objects',
            },
            'contract_request': {
                'generate': 'invoice_contract_generate', 'requests': 'ContractRequest.objects',
                'translation': 'translation',
            },
        }
        for entity, patches in cases.items():
            with self.subTest(entity=entity):
                holder = MagicMock(id=5)
                response, mocks = self.post(
                    {'entity': entity, 'object_id': 1, 'is_budget': True, 'holder_id': 5},
                    holder=holder, **patches,
                )

                self.assertEqual(response.status_code, 200)
                mocks['apply'].assert_called_once_with(mocks['generate'].return_value, holder)
                if entity == 'contract_request':
                    self.assertEqual(mocks['generate'].call_args.kwargs['new_holder'], 5)

    def test_contract_budget_uses_rebilling_holder_as_fallback(self):
        holder = MagicMock(id=7)
        reading = MagicMock(supply_point=None)
        reading.invoices.filter.return_value.first.return_value = None
        with patch(f'{VIEW}.Reading.objects') as readings:
            readings.get.return_value = reading
            response, mocks = self.post(
                {'entity': 'contract', 'object_id': 1, 'is_budget': True,
                 'redo_option': {'reason': 'holder', 'new_holder': 7, 'leak_consum': {'1': 0}}},
                holder=holder, generate='generate_consumption_invoice_multiple',
                contracts='Contract.objects',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mocks['generate'].call_args.kwargs['new_holder'], 7)
        mocks['apply'].assert_called_once_with(mocks['generate'].return_value, holder)
