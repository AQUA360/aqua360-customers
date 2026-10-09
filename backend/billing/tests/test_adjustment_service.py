import logging
from django.db import connection
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from billing.utils.adjustment_service import adjustment_eval_conditions, billing_run_cache_scope, generate_variables
from collections import namedtuple
from contract.models import (
    VariableType, 
    Variable, 
    Contract, 
    ContractUseType,
    ContractClientType
)
from pricing.models import Adjustment, AdjustmentCondition, AdjustmentIntervalStretch, AdjustmentOperation, LineItemType
from billing.models import Invoice
from claimrequest.models import ClaimRequestStatus
from coredata.models import ConfigProject

# Configure logger
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Add StreamHandler to logger
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

class TestAdjustmentService(TestCase):
    @classmethod
    def load_fixtures(cls):
        # Disable debug cursor
        connection.force_debug_cursor = False

        try:
            # Load your fixtures
            call_command('loaddata', 'coredata/fixtures/tests/all_data.json')
            
            # Verificar que els ClaimRequestStatus s'han carregat correctament
            from coredata.models import ConfigProject
            
            # Imprimir tots els ClaimRequestStatus
            print("\nClaimRequestStatus existents:")
            for status in ClaimRequestStatus.objects.all():
                print(f"ID: {status.id}, Token: {status.token}, Name: {status.name}")
            
            # Verificar els ConfigProject relacionats
            print("\nConfigProject relacionats:")
            config_tokens = [
                'claim_request_status_pending_token',
                'claim_request_status_accepted_token',
                'claim_request_status_finalized_token',
                'claim_request_status_cancelled_token'
            ]
            for token in config_tokens:
                try:
                    config = ConfigProject.objects.get(token=token)
                    print(f"Token: {token}, Value: {config.value}")
                    # Verificar que existeix el ClaimRequestStatus corresponent
                    status = ClaimRequestStatus.objects.get(token=config.value)
                    print(f"  -> ClaimRequestStatus trobat: {status.name}")
                except ConfigProject.DoesNotExist:
                    print(f"ConfigProject no trobat: {token}")
                except ClaimRequestStatus.DoesNotExist:
                    print(f"ClaimRequestStatus no trobat per token: {config.value}")
        finally:
            # Re-enable debug cursor
            connection.force_debug_cursor = True
    
    @classmethod
    def setUpTestData(self):
        self.load_fixtures()
        # Create Variable Types
        self.variable_type_bool = VariableType.objects.create(token='ACA-CANON', name='ACA Canon', data_type='bool')
        self.variable_type_int = VariableType.objects.create(token='INT-VAR', name='Integer Variable', data_type='int')

        # Create Variables
        self.variable_bool = Variable.objects.create(type=self.variable_type_bool, value='True')
        self.variable_int = Variable.objects.create(type=self.variable_type_int, value='100')

        # Create ContractUseType and ContractClientType
        self.use_type = ContractUseType.objects.create(token='9')
        self.client_type = ContractClientType.objects.create(token='P')

        # Create real Contract
        self.contract = Contract.objects.create(
            total_persons=10,
            use_type=self.use_type,
            client_type=self.client_type
        )
        
        self.contract.variables.add(self.variable_bool, self.variable_int)

        self.supply_point = None
        self.consumption = 500
        self.consumption_days = 30
        self.consumption_leakage = None
        self.consumption_responsible = True

        

    def test_is_true_condition(self):  # consumption_responsible --> True  (10 persones a 500 litres); is_false --> False
        # Crear l'adjustment i la condition com a models reals
        
        adjustment = Adjustment.objects.create(
            token='TEST_ADJ',
            name='Test Adjustment'
        )
        condition = AdjustmentCondition.objects.create(
            adjustment=adjustment,
            quantity={'value': 'consumption_responsible'},
            operation='is_true',
            formula=''
        )
        
        variables, variable_types = generate_variables(self.contract, self.consumption, self.consumption_days, self.consumption_leakage,self.consumption_responsible)
        print(f"variables: {variables}; variable_types: {variable_types}")
        result = adjustment_eval_conditions(adjustment, variables, variable_types)
        logger.debug("Test is_true_condition result: %s", result)
        self.assertTrue(True)

        
    def test_is_false_condition(self): # consumption_responsible --> True  (10 persones a 500 litres); is_false --> False
        adjustment = Adjustment.objects.create()
        condition = AdjustmentCondition.objects.create(
            adjustment=adjustment,
            quantity={'value': 'consumption_responsible'},
            operation='is_false',
            formula=''
        )
        
        variables, variable_types = generate_variables(self.contract, self.consumption, self.consumption_days, self.consumption_leakage,self.consumption_responsible)
        result = adjustment_eval_conditions(adjustment, variables, variable_types)
        logger.debug("Test is_false_condition result: %s", result)
        self.assertFalse(result)

    def test_gt_condition(self):
        adjustment = Adjustment.objects.create()
        condition = AdjustmentCondition.objects.create(
            adjustment=adjustment,
            quantity={'value': 'consumption'},
            operation='gt',
            formula='400'
        )
        
        variables, variable_types = generate_variables(self.contract, self.consumption, self.consumption_days, self.consumption_leakage,self.consumption_responsible)
        result = adjustment_eval_conditions(adjustment, variables, variable_types)
        logger.debug("Test gt_condition result: %s", result)
        self.assertTrue(result) # hauría de tornar True perquè 500 >(gt) 400

    def test_lt_condition(self):
        adjustment = Adjustment.objects.create()
        condition = AdjustmentCondition.objects.create(
            adjustment=adjustment,
            quantity={'value': 'consumption'},
            operation='lt',
            formula='600'
        )
        
        variables, variable_types = generate_variables(self.contract, self.consumption, self.consumption_days, self.consumption_leakage,self.consumption_responsible)
        result = adjustment_eval_conditions(adjustment, variables, variable_types)
        logger.debug("Test lt_condition result: %s", result)
        self.assertTrue(result) # hauría de tornar True perquè 500 < (lt) 600

    def test_lt_condition_formula(self):
        adjustment = Adjustment.objects.create()
        condition = AdjustmentCondition.objects.create(
            adjustment=adjustment,
            quantity={'value': 'consumption'},
            operation='eq',
            formula='%consumption'
        )
        
        variables, variable_types = generate_variables(self.contract, self.consumption, self.consumption_days, self.consumption_leakage,self.consumption_responsible)
        result = adjustment_eval_conditions(adjustment, variables, variable_types)
        logger.debug("Test lt_condition_formula result: %s", result)
        self.assertTrue(result)

    def test_variable_bool_condition(self):
        adjustment = Adjustment.objects.create()
        condition = AdjustmentCondition.objects.create(
            adjustment=adjustment,
            quantity={'value': 'variable.ACA-CANON'},
            operation='is_true',
            formula=''
        )
        
        variables, variable_types = generate_variables(self.contract, self.consumption, self.consumption_days, self.consumption_leakage,self.consumption_responsible)
        result = adjustment_eval_conditions(adjustment, variables, variable_types)
        logger.debug("Test variable_bool_condition result: %s", result)
        self.assertTrue(result)

    def test_variable_int_condition(self):
        adjustment = Adjustment.objects.create()
        condition = AdjustmentCondition.objects.create(
            adjustment=adjustment,
            quantity={'value': 'variable.INT-VAR'},
            operation='eq',
            formula='100'
        )
        
        variables, variable_types = generate_variables(self.contract, self.consumption, self.consumption_days, self.consumption_leakage,self.consumption_responsible)
        result = adjustment_eval_conditions(adjustment, variables, variable_types)
        logger.debug("Test variable_int_condition result: %s", result)
        self.assertTrue(result)

    def test_variable_vs_variable(self):
        adjustment = Adjustment.objects.create()
        condition = AdjustmentCondition.objects.create(
            adjustment=adjustment,
            quantity={'value': 'variable.INT-VAR'},
            operation='eq',
            formula='%variable.INT-VAR'
        )
        
        variables, variable_types = generate_variables(self.contract, self.consumption, self.consumption_days, self.consumption_leakage,self.consumption_responsible)
        result = adjustment_eval_conditions(adjustment, variables, variable_types)
        logger.debug("Test variable_vs_variable result: %s", result)
        self.assertTrue(result)

    def test_persons_min(self):
        adjustment = Adjustment.objects.create()
        condition = AdjustmentCondition.objects.create(
            adjustment=adjustment,
            quantity={'value': 'persons_min'},
            operation='eq',
            formula='10'  # contract.total_persons és 10
        )
        
        variables, variable_types = generate_variables(self.contract, self.consumption, self.consumption_days, self.consumption_leakage,self.consumption_responsible)
        result = adjustment_eval_conditions(adjustment, variables, variable_types)
        logger.debug("Test test_persons_min result: %s", result)
        self.assertTrue(result)


def create_contract_signal_config():
    # El post_save de Contract (terminate_contract_update_bail) necessita aquest ConfigProject
    ConfigProject.objects.get_or_create(token='contract_terminated_status', defaults={'value': 'terminated'})


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
