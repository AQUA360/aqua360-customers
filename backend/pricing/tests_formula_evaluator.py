import importlib

from django.apps import apps
from django.test import SimpleTestCase, TestCase

from billing.utils.adjustment_service import evaluate_formula
from pricing.models import Adjustment, AdjustmentCondition, AdjustmentIntervalStretch, LineItemType
from pricing.serializers.value_objects_serializer import AdjustmentIntervalStretchSerializer
from pricing.utils.formula_evaluator import ERROR_MESSAGES, FormulaError, evaluate, validate


DAYS_CORRECTION = 'math.ceil(9 * %contract.persons * (%consumption_days / 90 if abs(%consumption_days / 90 - 1) > 0.2 else 1))'


class EvaluateFormulaTest(SimpleTestCase):
    def test_days_correction_formula(self):
        for persons, days, expected in [(3, 90, 27), (3, 60, 18), (4, 120, 48), (5, 100, 45), (2, 30, 6), (0, 75, 0)]:
            with self.subTest(persons=persons, days=days):
                variables = {'contract.persons': persons, 'consumption_days': days}
                self.assertEqual(evaluate(DAYS_CORRECTION, variables), expected)

    def test_same_results_as_before(self):
        variables = {
            'contract.persons': 4,
            'consumption': 37.5,
            'consumption_days': 61,
            'variable.5021': '2',
            'variable.AMPLIACIO': '1.5',
            'contract.communication_type': 'PAPER',
        }
        cases = [
            ('%consumption', 37.5),
            ('( 9 * %contract.persons ) * %consumption_days / 90', 9 * 4 * 61 / 90),
            ('27*%variable.5021', 54),
            ('18 * %contract.persons * %variable.AMPLIACIO', 108.0),
            ('27 + ( ( %contract.persons - 4 ) *  9) + 18 + 9', 54),
            ('0.3999', 0.3999),
            ("1 if '%contract.communication_type' == 'PAPER' else 0", 1),
            ('%contract.persons > 3 and %consumption < 40', True),
            ('(0.21) * %consumption', 0.21 * 37.5),
        ]
        for formula, expected in cases:
            with self.subTest(formula=formula):
                self.assertEqual(evaluate(formula, variables), expected)

    def test_rejects_code(self):
        formulas = [
            "__import__('os').system('id')",
            "open('/etc/passwd').read()",
            '().__class__.__base__.__subclasses__()',
            'math.__dict__',
            '(lambda: 1)()',
            '[1, 2][0]',
            'max(*[1] * 10**9)',
            'x + 1',
        ]
        for formula in formulas:
            with self.subTest(formula=formula):
                with self.assertRaises(FormulaError):
                    evaluate(formula, {})

    def test_rejects_huge_results(self):
        for formula in ['9**9**9', '(10**15)**100', "'a' * 10**9", '-' * 999 + '1']:
            with self.subTest(formula=formula[:20]):
                with self.assertRaises(FormulaError):
                    evaluate(formula, {})

    def test_round_with_huge_digits_is_rejected(self):
        for formula in ['round(1, -10**7)', 'round(%consumption, 10**7)']:
            with self.subTest(formula=formula):
                with self.assertRaises(FormulaError):
                    evaluate(formula, {'consumption': 1})
        self.assertEqual(evaluate('round(%consumption, 2)', {'consumption': 1.2345}), 1.23)

    def test_quoted_variable_is_text(self):
        variables = {'contract.zip': '08001', 'contract.persons': 3}
        self.assertIs(evaluate("'%contract.zip' == '08001'", variables), True)
        self.assertIs(evaluate("'%contract.persons' == '3'", variables), True)

    def test_decimal_comma_is_an_error(self):
        with self.assertRaisesMessage(FormulaError, 'punt'):
            evaluate('0,5', {})

    def test_variable_value_is_not_code(self):
        with self.assertRaises(FormulaError):
            evaluate('%contract.communication_type + 1', {'contract.communication_type': "__import__('os')"})

    def test_unknown_variable(self):
        with self.assertRaisesMessage(FormulaError, '%consumption'):
            evaluate('%consumption * 2', {})

    def test_evaluate_formula_returns_false_on_error(self):
        with self.assertLogs('billing.utils.adjustment_service', level='ERROR'):
            self.assertIs(evaluate_formula("__import__('os')", {}), False)
        self.assertEqual(evaluate_formula('2 * %consumption', {'consumption': 3}), 6)


class ValidateFormulaTest(SimpleTestCase):
    def test_validate_accepts_any_variable(self):
        self.assertIsNone(validate(DAYS_CORRECTION))
        self.assertIsNone(validate('%consumption / (%variable.CASES - 1)'))

    def test_validate_checks_branches_not_taken(self):
        self.assertEqual(validate("1 if True else __import__('os')"), ERROR_MESSAGES['not_allowed'])

    def test_validate_checks_function_arguments(self):
        for formula in ['max(1)', 'max()', 'round(1, 2, 3)', 'abs()', 'math.ceil(1, 2)']:
            with self.subTest(formula=formula):
                self.assertEqual(validate(formula), ERROR_MESSAGES['arguments'])
        self.assertIsNone(validate('max(%a, %b, 3)'))
        self.assertIsNone(validate('round(%a)'))

    def test_validate_message_has_no_internal_details(self):
        self.assertEqual(validate('1 +'), ERROR_MESSAGES['syntax'])
        self.assertEqual(validate('0,5'), ERROR_MESSAGES['decimal_comma'])

    def test_serializer_rejects_invalid_formula(self):
        serializer = AdjustmentIntervalStretchSerializer(data={'formula': "__import__('os')"})
        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors['formula'], [ERROR_MESSAGES['not_allowed']])


class FixDecimalCommaMigrationTest(TestCase):
    def test_only_plain_numbers_with_comma_are_fixed(self):
        adjustment = Adjustment.objects.create(formula='0,5')
        stretch = AdjustmentIntervalStretch.objects.create(formula=' 1,25 ')
        line_item_type = LineItemType.objects.create(formula='max(1,5)')
        condition = AdjustmentCondition.objects.create(formula='1,2')

        migration = importlib.import_module('pricing.migrations.0132_formula_decimal_comma')
        migration.fix_decimal_comma(apps, None)

        for item, expected in [(adjustment, '0.5'), (stretch, '1.25'), (line_item_type, 'max(1,5)'), (condition, '1,2')]:
            item.refresh_from_db()
            self.assertEqual(item.formula, expected)
