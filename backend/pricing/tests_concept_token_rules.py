from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from pricing.models import AccountingConcept, AccountingPricing, AccountingType
from pricing.utils.accounting_service import (
    _bucket_concept_override,
    _declare_invoice,
    _ensure_invoice_group,
    _get_invoice_category_line,
    _invoice_group_key,
    _line_concept_token,
    _match_concept_token_rule,
    _matched_concept_rule,
    _normalize_concept_token_rules,
    _pad_account_code,
)
from service.models import Company, Exploitation


def _pricing_stub(*, concept_token='430', token='2000', token_return=None, token_return_invoice=None):
    concept = SimpleNamespace(token=concept_token, name='Clients', category='invoice')
    return SimpleNamespace(
        accounting_concept=concept,
        token=token,
        token_return=token_return,
        token_return_invoice=token_return_invoice,
        token_return_payment=None,
        token_return_lineitem=None,
    )


class ConceptTokenRuleHelpersTests(SimpleTestCase):
    def test_normalize_keeps_order_and_drops_invalid(self):
        rules = _normalize_concept_token_rules([
            {'field': 'customer_token_final', 'op': 'contains', 'value': 'X', 'concept_token': '8', 'position': 2},
            {'field': 'unknown', 'op': 'eq', 'value': 'a', 'concept_token': '1'},
            {'field': 'customer_token_final', 'op': 'eq', 'value': 'X12345678', 'concept_token': '9', 'position': 0},
            'bad',
        ])
        self.assertEqual([rule['concept_token'] for rule in rules], ['9', '8'])
        self.assertEqual([rule['position'] for rule in rules], [0, 1])

    def test_match_ops_and_first_wins(self):
        rules = _normalize_concept_token_rules([
            {
                'field': 'customer_token_final',
                'op': 'eq',
                'value': 'X12345678',
                'concept_token': '9',
            },
            {
                'field': 'customer_token_final',
                'op': 'startswith',
                'value': 'X',
                'concept_token': '8',
            },
            {
                'field': 'payer_token_final',
                'op': 'contains',
                'value': '99',
                'concept_token': '7',
            },
            {
                'field': 'origin_id',
                'op': 'eq',
                'value': '12',
                'concept_token': '6',
            },
        ])
        self.assertEqual(
            _match_concept_token_rule(rules, {'customer_token_final': 'X12345678'})['concept_token'],
            '9',
        )
        self.assertEqual(
            _match_concept_token_rule(rules, {'customer_token_final': 'X999'})['concept_token'],
            '8',
        )
        self.assertEqual(
            _match_concept_token_rule(rules, {'payer_token_final': 'AB99CD'})['concept_token'],
            '7',
        )
        self.assertEqual(
            _match_concept_token_rule(rules, {'origin_id': 12})['concept_token'],
            '6',
        )
        self.assertIsNone(_match_concept_token_rule(rules, {'customer_token_final': 'A1'}))

    def test_pad_account_code(self):
        self.assertEqual(_pad_account_code('430', '2000'), '430000002000')
        self.assertEqual(_pad_account_code('9', '2000'), '900000002000')

    def test_line_concept_token_override_respects_apply_to_return(self):
        pricing = _pricing_stub(token_return='477')
        override = {
            'concept_token': '9',
            'apply_to_return': False,
            'source': 'own',
        }
        self.assertEqual(_line_concept_token(pricing, 35, concept_override=override), '9')
        self.assertEqual(
            _line_concept_token(pricing, -35, concept_override=override),
            '477',
        )
        override_return = {**override, 'apply_to_return': True}
        self.assertEqual(
            _line_concept_token(pricing, -35, concept_override=override_return),
            '9',
        )

    def test_main_source_does_not_change_own_concept(self):
        pricing = _pricing_stub()
        override = {
            'concept_token': '9',
            'apply_to_return': True,
            'source': 'main',
        }
        self.assertEqual(_line_concept_token(pricing, 35, concept_override=override), '430')

    def test_invoice_group_key_splits_by_rule(self):
        spec = {
            'separate_by_origin': False,
            'concept_token_rules': _normalize_concept_token_rules([
                {
                    'field': 'customer_token_final',
                    'op': 'eq',
                    'value': 'X12345678',
                    'concept_token': '9',
                },
            ]),
            'main_concept_token_rules': [],
        }
        matched = _invoice_group_key(spec, {'customer_token_final': 'X12345678'})
        unmatched = _invoice_group_key(spec, {'customer_token_final': '112233745G'})
        self.assertNotEqual(matched, unmatched)
        self.assertIsNone(unmatched)
        self.assertEqual(matched[1][1], '9')

    def test_matched_concept_rule_prefers_own_over_main(self):
        spec = {
            'concept_token_rules': _normalize_concept_token_rules([
                {
                    'field': 'customer_token_final',
                    'op': 'eq',
                    'value': 'X12345678',
                    'concept_token': '9',
                },
            ]),
            'main_concept_token_rules': _normalize_concept_token_rules([
                {
                    'field': 'customer_token_final',
                    'op': 'eq',
                    'value': 'X12345678',
                    'concept_token': '5',
                },
            ]),
        }
        matched = _matched_concept_rule(spec, {'customer_token_final': 'X12345678'})
        self.assertEqual(matched['concept_token'], '9')
        self.assertEqual(matched['source'], 'own')


class ConceptTokenRuleSplitTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Aigües Test', vat='B00000001')
        self.exploitation = Exploitation.objects.create(token='EXP1', name='Explotació 1')
        self.accounting_type = AccountingType.objects.create(
            token='clients',
            name='Clients',
            add_taxes=True,
            add_subtotals=True,
        )
        self.iva_type = AccountingType.objects.create(
            token='iva',
            name='IVA',
            add_taxes=True,
            add_subtotals=False,
        )
        self.clients_concept = AccountingConcept.objects.create(
            token='430',
            name='Clients',
            category='invoice',
            type=self.accounting_type,
        )
        self.iva_concept = AccountingConcept.objects.create(
            token='477',
            name='IVA',
            category='invoice',
            type=self.iva_type,
        )
        self.clients_pricing = AccountingPricing.objects.create(
            token='2000',
            name='Abonats',
            accounting_concept=self.clients_concept,
            company=self.company,
            exploitation=self.exploitation,
            is_default=True,
            concept_token_rules=[
                {
                    'field': 'customer_token_final',
                    'op': 'eq',
                    'value': 'X12345678',
                    'concept_token': '9',
                    'apply_to_return': False,
                    'position': 0,
                },
            ],
        )
        self.iva_pricing = AccountingPricing.objects.create(
            token='0000',
            name='IVA',
            accounting_concept=self.iva_concept,
            company=self.company,
            exploitation=self.exploitation,
            is_default=False,
        )

    def test_declare_invoice_splits_matched_amounts(self):
        from pricing.utils.accounting_service import _invoice_spec

        spec = _invoice_spec(self.clients_pricing, main_accounting=self.clients_pricing)
        buckets = {spec['id']: {}}
        rows = [
            {
                'id': 1,
                'exploitation_id': self.exploitation.id,
                'origin_id': None,
                'use_type_id': None,
                'subtotal_final': Decimal('45'),
                'total_final': Decimal('45'),
                'customer_token_final': '112233745G',
                'invoice_category': 'normal',
            },
            {
                'id': 2,
                'exploitation_id': self.exploitation.id,
                'origin_id': None,
                'use_type_id': None,
                'subtotal_final': Decimal('20'),
                'total_final': Decimal('20'),
                'customer_token_final': '875643351B',
                'invoice_category': 'normal',
            },
            {
                'id': 3,
                'exploitation_id': self.exploitation.id,
                'origin_id': None,
                'use_type_id': None,
                'subtotal_final': Decimal('35'),
                'total_final': Decimal('35'),
                'customer_token_final': 'X12345678',
                'invoice_category': 'normal',
            },
        ]
        tax_amounts = {}
        for row in rows:
            _declare_invoice(buckets, [spec], row, tax_amounts, 1, {})

        groups = buckets[spec['id']]
        self.assertEqual(len(groups), 2)
        totals = sorted(float(bucket['total']) for bucket in groups.values())
        self.assertEqual(totals, [35.0, 65.0])

        lines = []
        for _key, bucket in groups.items():
            line = _get_invoice_category_line(
                self.clients_pricing,
                bucket,
                main_accounting=self.clients_pricing,
            )
            if line:
                lines.append(line)
        concepts = sorted(line['accounting_concept'] for line in lines)
        self.assertEqual(concepts, ['430', '9'])
        by_concept = {line['accounting_concept']: line['total'] for line in lines}
        self.assertEqual(by_concept['9'], 35.0)
        self.assertEqual(by_concept['430'], 65.0)

    def test_iva_line_gets_main_concept_override_for_counterpart(self):
        from pricing.utils.accounting_service import _invoice_spec

        iva_spec = _invoice_spec(self.iva_pricing, main_accounting=self.clients_pricing)
        self.assertTrue(iva_spec['main_concept_token_rules'])
        group_key = _invoice_group_key(
            iva_spec,
            {'customer_token_final': 'X12345678'},
        )
        override = _matched_concept_rule(
            iva_spec,
            {'customer_token_final': 'X12345678'},
        )
        self.assertEqual(override['source'], 'main')
        bucket = _ensure_invoice_group({}, group_key, concept_override=override)
        bucket['total'] = Decimal('5.70')
        bucket['subtotal'] = Decimal('0')
        bucket['iva_bases']['10.00'] = {
            'base': Decimal('57.00'),
            'tax': Decimal('5.70'),
        }
        line = _get_invoice_category_line(
            self.iva_pricing,
            bucket,
            main_accounting=self.clients_pricing,
        )
        self.assertEqual(line['accounting_concept'], '477')
        self.assertEqual(line['main_concept_token_override'], '9')
        self.assertEqual(
            _pad_account_code(line['main_concept_token_override'], self.clients_pricing.token),
            '900000002000',
        )

    def test_bucket_override_roundtrip(self):
        override = {
            'concept_token': '9',
            'apply_to_return': True,
            'source': 'own',
        }
        bucket = _ensure_invoice_group({}, 'rule', concept_override=override)
        restored = _bucket_concept_override(bucket)
        self.assertEqual(restored['concept_token'], '9')
        self.assertTrue(restored['apply_to_return'])
        self.assertEqual(restored['source'], 'own')
