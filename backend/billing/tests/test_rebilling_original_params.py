from django.test import TestCase
from unittest.mock import MagicMock, patch


class RecalculationStrategyPersonsTest(TestCase):
    """ACUSTOMERS-334: verify persons resolution and tariff selection on rebilling."""

    def test_generate_variables_uses_effective_persons_for_original(self):
        from billing.utils.adjustment_service import generate_variables
        contract = MagicMock()
        contract.total_persons = 2
        invoice = MagicMock()
        invoice.persons_final = 4
        vars_result, _ = generate_variables(
            contract, 100, 30,
            invoice=invoice,
            recalculation_strategy="original",
            effective_persons=4,
        )
        self.assertEqual(vars_result['contract.total_persons'], 4)
        self.assertEqual(vars_result['contract.persons'], 4)

    def test_generate_variables_fallback_current(self):
        from billing.utils.adjustment_service import generate_variables
        contract = MagicMock()
        contract.total_persons = 2
        vars_result, _ = generate_variables(
            contract, 100, 30,
            invoice=None,
            recalculation_strategy="current",
        )
        self.assertEqual(vars_result['contract.total_persons'], 2)

    def test_tariff_option_a_from_original_line_items(self):
        from billing.utils.invoice_service import _group_recalculation_price_rates

        contract = MagicMock()
        contract_rate = MagicMock(price_rate=MagicMock(id=42), supply_point='current-sp')
        price_rates = MagicMock()
        price_rates.order_by.return_value = price_rates
        price_rates.__iter__.return_value = iter([contract_rate])
        price_rates.values_list.return_value = [42]
        contract.price_rates.filter.return_value = price_rates

        original_inv = MagicMock()
        original_inv.line_items.filter.return_value.values_list.return_value.distinct.return_value = [42]
        original_inv.line_items.filter.return_value.exists.return_value = True
        with patch('billing.utils.invoice_service.Invoice.objects.filter') as invoice_filter:
            invoice_filter.return_value.first.return_value = original_inv
            grouped = _group_recalculation_price_rates(contract, '01000058023', 'original')

        self.assertEqual(grouped['current-sp'], [contract_rate.price_rate])
        invoice_filter.assert_called_once_with(token='01000058023')

    def test_tariff_current_strategy_populates_supply_point_group(self):
        from billing.utils.invoice_service import _group_recalculation_price_rates

        contract = MagicMock()
        contract_rate = MagicMock(price_rate=MagicMock(id=7), supply_point='current-sp')
        price_rates = MagicMock()
        price_rates.order_by.return_value = price_rates
        price_rates.__iter__.return_value = iter([contract_rate])
        contract.price_rates.filter.return_value = price_rates

        grouped = _group_recalculation_price_rates(contract, None, 'current')

        self.assertEqual(grouped, {'current-sp': [contract_rate.price_rate]})

    def test_tariff_original_strategy_adds_missing_historical_rate(self):
        from billing.utils.invoice_service import _group_recalculation_price_rates

        contract = MagicMock()
        contract.supply_points.exists.return_value = True
        contract.supply_points.first.return_value = 'contract-sp'
        price_rates = MagicMock()
        price_rates.order_by.return_value = price_rates
        price_rates.__iter__.return_value = iter([])
        price_rates.values_list.return_value = []
        contract.price_rates.filter.return_value = price_rates

        original_inv = MagicMock()
        original_inv.line_items.filter.return_value.exists.return_value = True
        original_inv.line_items.filter.return_value.values_list.return_value.distinct.return_value = [99]
        historical_rate = MagicMock(id=99)

        with patch('billing.utils.invoice_service.Invoice.objects.filter') as invoice_filter, \
                patch('billing.utils.invoice_service.PriceRate.objects.filter', return_value=[historical_rate]):
            invoice_filter.return_value.first.return_value = original_inv
            grouped = _group_recalculation_price_rates(contract, '01000058023', 'original')

        self.assertEqual(grouped, {'contract-sp': [historical_rate]})
        invoice_filter.assert_called_once_with(token='01000058023')

    def test_legacy_invoice_occupants_are_recovered(self):
        from billing.utils.invoice_service import _resolve_recalculation_persons

        contract = MagicMock(total_persons=2)
        original_inv = MagicMock(persons_final=None)
        original_inv.line_items.filter.return_value.first.return_value = MagicMock(units=4)

        with patch('billing.utils.invoice_service.Invoice.objects.filter') as invoice_filter:
            invoice_filter.return_value.first.return_value = original_inv
            effective_persons = _resolve_recalculation_persons(
                contract, '01000058023', 'original'
            )

        self.assertEqual(effective_persons, 4)
        invoice_filter.assert_called_once_with(token='01000058023')

    def test_line_item_quantity_uses_effective_persons(self):
        from billing.utils.invoice_line_item_service import create_from_lineitemtype
        contract = MagicMock()
        contract.total_persons = 2
        line_item_type = MagicMock()
        line_item_type.price = None
        line_item_type.proportional_price = 1
        line_item_type.price_interval = None
        line_item_type.active_choice = None
        line_item_type.inactive_choice = None
        line_item_type.is_prorated = False
        line_item_type.billing_period = None
        line_item_type.quantity.token = 'total_persons'
        # create_from_lineitemtype returns line_items; with total_persons qty,
        # the internal quantitat variable should be 4 when effective_persons=4.
        # We verify via direct inspection of the quantity logic by mocking.
        result = create_from_lineitemtype(
            contract, line_item_type, None, 100, 30,
            effective_persons=4,
            recalculation_strategy="original",
        )
        self.assertTrue(result)
        self.assertTrue(all(line_item['units'] == 4 for line_item in result))
