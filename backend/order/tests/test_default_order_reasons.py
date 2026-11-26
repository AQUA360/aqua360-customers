"""Motius d'ordre per defecte (2994): migració de neteja i vista inversa."""
import importlib
import json
from pathlib import Path

from django.apps import apps
from django.test import TestCase

from order.models import OrderReason, OrderType
from order.serializers.value_objects_serializer import (
    OrderReasonSerializer,
    OrderTypeSerializer,
)

migration = importlib.import_module('order.migrations.0037_default_order_reasons_cleanup')


class DefaultOrderReasonsMigrationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.types = {
            token: OrderType.objects.create(token=token, name=token)
            for token in ('cut_supply', 'remove_meter', 'restore_meter', 'restore_supply')
        }
        cls.owner = OrderReason.objects.create(token='canvi_titular', name='CANVI DE TITULAR')
        cls.termination = OrderReason.objects.create(token='contract_termination', name='BAIXA')
        cls.termination.type.set([
            cls.types['cut_supply'], cls.types['restore_meter'], cls.types['restore_supply'],
        ])

    def test_forwards_renames_token_and_remaps_termination(self):
        migration.forwards(apps, None)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.token, 'change_of_owner')
        self.assertEqual(
            set(self.termination.type.values_list('token', flat=True)),
            {'cut_supply', 'remove_meter'},
        )

    def test_forwards_is_idempotent(self):
        migration.forwards(apps, None)
        migration.forwards(apps, None)
        self.assertEqual(self.termination.type.count(), 2)
        self.assertEqual(OrderReason.objects.filter(token='change_of_owner').count(), 1)

    def test_forwards_does_not_rename_when_new_token_exists(self):
        OrderReason.objects.create(token='change_of_owner', name='ja existent')
        migration.forwards(apps, None)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.token, 'canvi_titular')

    def test_backwards_restores_token(self):
        migration.forwards(apps, None)
        migration.backwards(apps, None)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.token, 'canvi_titular')


class OrderReasonReverseViewTestCase(TestCase):
    def test_reason_serializer_lists_its_types(self):
        order_type = OrderType.objects.create(token='remove_meter', name='Retirada')
        reason = OrderReason.objects.create(token='contract_termination', name='Baixa')
        reason.type.set([order_type])
        data = OrderReasonSerializer(reason).data
        self.assertEqual([t['token'] for t in data['types']], ['remove_meter'])

    def test_type_serializer_lists_its_reasons(self):
        order_type = OrderType.objects.create(token='remove_meter', name='Retirada')
        reason = OrderReason.objects.create(token='contract_termination', name='Baixa')
        reason.type.set([order_type])
        data = OrderTypeSerializer(order_type).data
        self.assertEqual([r['token'] for r in data['reasons']], ['contract_termination'])


class DefaultFixturesTestCase(TestCase):
    def test_fixtures_use_english_tokens_and_valid_types(self):
        base = Path(__file__).resolve().parents[2] / 'initial_data'
        for lang in ('ca', 'es'):
            reasons = json.loads((base / lang / 'order.OrderReason.json').read_text())
            type_pks = {t['pk'] for t in json.loads((base / lang / 'order.OrderType.json').read_text())}
            type_tokens = {t['pk']: t['fields']['token'] for t in json.loads((base / lang / 'order.OrderType.json').read_text())}
            for r in reasons:
                token = r['fields']['token']
                self.assertTrue(token.isascii() and token == token.lower(), token)
                self.assertTrue(set(r['fields']['type']) <= type_pks, (lang, token))
                if token == 'contract_termination':
                    self.assertEqual(
                        {type_tokens[p] for p in r['fields']['type']},
                        {'cut_supply', 'remove_meter'},
                    )
