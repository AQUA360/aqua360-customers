from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase

from billing.views.generate_invoice_budget_view import GenerateInvoiceBudgetView


class GenerateInvoiceBudgetStrategyTest(TestCase):
    def test_pending_readings_and_redo_options_select_the_expected_strategy(self):
        for redo, expected in (
            (None, 'current'),
            ({'invoice_token': 'original', 'reason': 'other'}, 'original'),
            ({'invoice_token': 'original', 'reason': 'other', 'recalculation_strategy': 'current'}, 'current'),
        ):
            with self.subTest(redo=redo):
                reading = MagicMock(supply_point=None)
                reading.invoices.filter.return_value.first.return_value = None
                data = {'entity': 'contract', 'object_id': 1, 'is_budget': True}
                if redo:
                    data['redo_option'] = dict(redo, leak_consum={'1': 0})
                with patch('billing.views.generate_invoice_budget_view.ConfigProject.objects.get'), \
                        patch('billing.views.generate_invoice_budget_view.Contract.objects.get'), \
                        patch('billing.views.generate_invoice_budget_view.Reading.objects') as readings, \
                        patch('billing.views.generate_invoice_budget_view.generate_consumption_invoice_multiple') as generate, \
                        patch('billing.views.generate_invoice_budget_view.InvoiceFullSerializer') as serializer, \
                        patch('billing.views.generate_invoice_budget_view.disconnect_payment_signals'), \
                        patch('billing.views.generate_invoice_budget_view.reconnect_payment_signals'):
                    readings.get.return_value = reading
                    readings.filter.return_value.order_by.return_value = [reading]
                    serializer.return_value.data = {'id': 1}
                    response = GenerateInvoiceBudgetView().post(SimpleNamespace(data=data))

                self.assertEqual(response.status_code, 200)
                self.assertEqual(generate.call_args.kwargs['recalculation_strategy'], expected)
