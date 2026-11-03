"""Cobertura de la parella type/reason lliure al OrderSaveSerializer (2287).

Els formularis manuals permeten triar qualsevol motiu sense dependre del
tipus d'ordre: un motiu que NO està vinculat (M2M) al tipus seleccionat
s'ha de poder desar sense errors de validació. La inferència de motiu
del create() només s'aplica quan el camp ve absent i el tipus té exactament
un motiu vinculat; mai rebutja una parella discrepant.
"""
from django.test import TestCase

from coredata.models import ConfigProject
from order.models import Order, OrderReason, OrderStatus, OrderType
from order.serializers.order_serializer import OrderSaveSerializer


class OrderSaveSerializerFreeReasonTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.type_a = OrderType.objects.create(token='T-2287-A', name='Tipus A')
        cls.type_b = OrderType.objects.create(token='T-2287-B', name='Tipus B')
        cls.reason_x = OrderReason.objects.create(token='R-2287-X', name='Motiu X')
        cls.reason_y = OrderReason.objects.create(token='R-2287-Y', name='Motiu Y')
        # reason_y només està vinculat a type_b.
        cls.reason_y.type.set([cls.type_b])
        cls.default_status = OrderStatus.objects.create(
            token='2287-default', name='Per defecte', is_default=True,
        )
        # Quan RABBITMQ_ENABLED és true, create() substitueix l'estat pel
        # token de ConfigProject: fixtures perquè el test no depengui de l'entorn.
        ConfigProject.objects.get_or_create(
            token='sent_order_status_token', defaults={'value': '2287-default'},
        )

    def _save(self, **fields):
        payload = {'token': 'DRAFT-2287'}
        payload.update(fields)
        serializer = OrderSaveSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    def test_arbitrary_type_reason_pair_saves(self):
        order = self._save(type=self.type_a.id, reason=self.reason_y.id)
        self.assertIsInstance(order, Order)
        order.refresh_from_db()
        self.assertEqual(order.type_id, self.type_a.id)
        self.assertEqual(order.reason_id, self.reason_y.id)

    def test_reason_inference_still_fills_single_linked_reason(self):
        # type_b té exactament un motiu vinculat (reason_y): sense reason al
        # payload, la inferència existent l'omple. type_a no en té cap.
        order = self._save(type=self.type_b.id)
        order.refresh_from_db()
        self.assertEqual(order.reason_id, self.reason_y.id)

        order_no_reasons = self._save(type=self.type_a.id)
        order_no_reasons.refresh_from_db()
        self.assertIsNone(order_no_reasons.reason_id)
