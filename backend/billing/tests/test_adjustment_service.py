from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from billing.utils.adjustment_service import billing_run_cache_scope, generate_variables
from contract.models import Contract, Variable, VariableType
from coredata.models import ConfigProject
from pricing.models import (
    Adjustment,
    AdjustmentCondition,
    AdjustmentIntervalStretch,
    AdjustmentOperation,
    LineItemType,
)


def create_contract_signal_config():
    # El post_save de Contract (terminate_contract_update_bail) necessita aquest ConfigProject
    ConfigProject.objects.get_or_create(token='contract_terminated_status', defaults={'value': 'terminated'})


class TestContractMinPersons(TestCase):
    """El mínim de persones (persons_min) es configura amb el ConfigProject contract_min_persons."""

    @classmethod
    def setUpTestData(cls):
        create_contract_signal_config()
        ConfigProject.objects.filter(token='contract_min_persons').delete()
        cls.contract = Contract.objects.create(total_persons=2)

    def _variables(self, contract):
        variables, _ = generate_variables(contract, 10, 30)
        return variables

    def test_default_min_persons_without_config(self):
        variables = self._variables(Contract.objects.get(pk=self.contract.pk))
        self.assertEqual(variables['persons_min'], 3)

    def test_configured_min_persons(self):
        ConfigProject.objects.create(token='contract_min_persons', value='5')
        variables = self._variables(Contract.objects.get(pk=self.contract.pk))
        self.assertEqual(variables['persons_min'], 5)
        self.assertEqual(variables['contract.total_persons'], 2)
        self.assertEqual(variables['contract.persons'], 2)

    def test_contract_persons_above_min(self):
        ConfigProject.objects.create(token='contract_min_persons', value='1')
        variables = self._variables(Contract.objects.get(pk=self.contract.pk))
        self.assertEqual(variables['persons_min'], 2)

    def test_min_persons_without_contract(self):
        ConfigProject.objects.create(token='contract_min_persons', value='4')
        variables = self._variables(None)
        self.assertEqual(variables['persons_min'], 4)
        self.assertEqual(variables['contract.total_persons'], 4)

    def test_invalid_config_uses_default(self):
        for value in ('', 'abc', '0'):
            ConfigProject.objects.update_or_create(token='contract_min_persons', defaults={'value': value})
            variables = self._variables(Contract.objects.get(pk=self.contract.pk))
            self.assertEqual(variables['persons_min'], 3)

    def test_non_positive_contract_persons_use_configured_minimum(self):
        ConfigProject.objects.create(token='contract_min_persons', value='5')
        for total_persons in (0, -1):
            with self.subTest(total_persons=total_persons):
                self.contract.total_persons = total_persons
                variables = self._variables(self.contract)
                self.assertEqual(variables['contract.total_persons'], 5)
                self.assertEqual(variables['contract.persons'], 5)
                self.assertEqual(variables['persons_min'], 5)

    def test_config_changes_visible_without_scope(self):
        config = ConfigProject.objects.create(token='contract_min_persons', value='4')
        self.assertEqual(self._variables(self.contract)['persons_min'], 4)
        config.value = '6'
        config.save(update_fields=['value'])
        self.assertEqual(self._variables(self.contract)['persons_min'], 6)

    def test_config_changes_visible_in_next_billing_scope(self):
        config = ConfigProject.objects.create(token='contract_min_persons', value='4')
        with billing_run_cache_scope():
            self.assertEqual(self._variables(self.contract)['persons_min'], 4)
            config.value = '6'
            config.save(update_fields=['value'])
            self.assertEqual(self._variables(self.contract)['persons_min'], 4)
        with billing_run_cache_scope():
            self.assertEqual(self._variables(self.contract)['persons_min'], 6)

    def test_config_queried_once_per_billing_scope(self):
        ConfigProject.objects.create(token='contract_min_persons', value='4')
        with CaptureQueriesContext(connection) as ctx:
            with billing_run_cache_scope():
                for _ in range(2):
                    contract = Contract.objects.get(pk=self.contract.pk)
                    for _ in range(3):
                        self.assertEqual(self._variables(contract)['persons_min'], 4)
        count = sum(1 for q in ctx.captured_queries if 'FROM "coredata_configproject"' in q['sql'])
        self.assertEqual(count, 1)


class TestVariableQueryCaching(TestCase):
    """Les variables es consulten un cop per contracte i els tipus un cop per facturació."""

    @classmethod
    def setUpTestData(cls):
        create_contract_signal_config()
        cls.variable_type = VariableType.objects.create(token='INT-VAR', name='Integer Variable', data_type='int')
        cls.contracts = []
        for value in ('100', '200'):
            contract = Contract.objects.create(total_persons=4)
            contract.variables.add(Variable.objects.create(type=cls.variable_type, value=value))
            cls.contracts.append(contract)

    def _count_queries(self, table, func):
        with CaptureQueriesContext(connection) as ctx:
            func()
        return sum(1 for q in ctx.captured_queries if f'FROM "{table}"' in q['sql'])

    def _bill_lines(self, contracts, lines=3):
        results = []
        for contract in contracts:
            contract = Contract.objects.get(pk=contract.pk)  # instància nova, com a la facturació
            for _ in range(lines):
                variables, _ = generate_variables(contract, 10, 30)
                results.append(variables['variable.INT-VAR'])
        return results

    def test_contract_variables_queried_once_per_contract(self):
        count = self._count_queries('contract_variable', lambda: self._bill_lines(self.contracts))
        self.assertEqual(count, len(self.contracts))

    def test_variable_types_queried_once_per_contract_without_scope(self):
        count = self._count_queries('contract_variabletype', lambda: self._bill_lines(self.contracts))
        self.assertEqual(count, len(self.contracts))

    def test_variable_types_queried_once_per_billing_scope(self):
        results = []

        def run():
            with billing_run_cache_scope():
                results.extend(self._bill_lines(self.contracts))

        count = self._count_queries('contract_variabletype', run)
        self.assertEqual(count, 1)
        self.assertEqual(results, [100, 100, 100, 200, 200, 200])

    def test_scope_is_released_after_billing(self):
        with billing_run_cache_scope():
            self._bill_lines(self.contracts[:1])
        VariableType.objects.create(token='NEW-VAR', name='New Variable', data_type='int')
        variables, _ = generate_variables(Contract.objects.get(pk=self.contracts[0].pk), 10, 30)
        self.assertIn('variable.NEW-VAR', variables)


class TestAdjustmentQueryCaching(TestCase):
    """Els ajustaments, condicions i intervals es consulten un cop per facturació."""

    @classmethod
    def setUpTestData(cls):
        create_contract_signal_config()
        operation = AdjustmentOperation.objects.create(token='ptg', name='Percentatge')
        cls.line_item_type = LineItemType.objects.create(name='Test line')
        cls.adj_applies = Adjustment.objects.create(
            token='ADJ-APPLIES', name='Applies', operation=operation, quantity=0.5,
            line_item_type=cls.line_item_type, position=1,
        )
        AdjustmentCondition.objects.create(
            adjustment=cls.adj_applies, quantity={'value': 'consumption'}, operation='gt', formula='5', position=1,
        )
        cls.adj_skipped = Adjustment.objects.create(
            token='ADJ-SKIPPED', name='Skipped', operation=operation, quantity=0.1,
            line_item_type=cls.line_item_type, position=2,
        )
        AdjustmentCondition.objects.create(
            adjustment=cls.adj_skipped, quantity={'value': 'consumption'}, operation='lt', formula='5', position=1,
        )
        cls.adj_with_stretch = Adjustment.objects.create(
            token='ADJ-STRETCH', name='Stretch', operation=operation, quantity=0.1,
            line_item_type=cls.line_item_type, position=3,
        )
        AdjustmentIntervalStretch.objects.create(adjustment=cls.adj_with_stretch, coefficient=2)
        cls.contracts = [Contract.objects.create(total_persons=4) for _ in range(2)]

    def _bill_lines(self, lines=3):
        from billing.utils.invoice_line_item_service import calc_correctors_price
        results = []
        for contract in self.contracts:
            contract = Contract.objects.get(pk=contract.pk)
            line_item_type = LineItemType.objects.get(pk=self.line_item_type.pk)
            for _ in range(lines):
                variables, variable_types = generate_variables(contract, 10, 30)
                price, _, applied = calc_correctors_price(line_item_type, 100, variables, variable_types, contract)
                results.append((price, [a['adjustment'].token for a in applied]))
        return results

    def _count_queries(self, func):
        tables = ('pricing_adjustment', 'pricing_adjustmentcondition', 'pricing_adjustmentintervalstretch')
        with CaptureQueriesContext(connection) as ctx:
            func()
        return {t: sum(1 for q in ctx.captured_queries if f'FROM "{t}"' in q['sql']) for t in tables}

    def test_adjustments_queried_once_per_billing_scope(self):
        results = []

        def run():
            with billing_run_cache_scope():
                results.extend(self._bill_lines())

        counts = self._count_queries(run)
        self.assertEqual(counts, {
            'pricing_adjustment': 1,
            'pricing_adjustmentcondition': 1,
            'pricing_adjustmentintervalstretch': 1,
        })
        # Només s'aplica l'ajustament sense intervals que compleix la condició
        self.assertEqual(results, [(50.0, ['ADJ-APPLIES'])] * 6)

    def test_results_match_without_scope(self):
        with billing_run_cache_scope():
            cached = self._bill_lines(lines=1)
        self.assertEqual(self._bill_lines(lines=1), cached)

    def test_adjustment_changes_visible_in_next_billing(self):
        with billing_run_cache_scope():
            self._bill_lines(lines=1)
        Adjustment.objects.filter(pk=self.adj_applies.pk).update(quantity=0.25)
        with billing_run_cache_scope():
            results = self._bill_lines(lines=1)
        self.assertEqual(results[0], (25.0, ['ADJ-APPLIES']))
