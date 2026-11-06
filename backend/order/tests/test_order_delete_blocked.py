"""Cobertura de la supressió d'ordres (#2342) al OrderViewSet.destroy().

Regla acordada: només es pot eliminar una ordre en estat inicial
(Pendent, Esborrany o Enviada, que és amb qui la GMAO té la tasca despatxada
encara no presa). Es bloqueja amb 400 si l'ordre té informes, està completada
o el seu estat és En Curs ('5'), Per validar / Tancada (tokens de ConfigProject
'for_validate_order_status_token' / 'order_status_completed_token').

En eliminar correctament es publica l'event RabbitMQ 'order.deleted'
(amb l'order_token) perquè la GMAO cancel·li la tasca despatxada.

publish_order_deleted_event queda sempre patchejat: cap test ha d'arribar
a un broker real.
"""
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from coredata.models import ConfigProject
from order.models import Order, OrderReport, OrderStatus
from order.services.rabbit import publish_order_deleted_event
from order.views.order_view import OrderViewSet


class OrderDeleteBlockedTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ("sent_order_status_token", "2342-sent"),
            ("for_validate_order_status_token", "2342-validate"),
            ("order_status_completed_token", "2342-completed"),
        ):
            ConfigProject.objects.get_or_create(
                token=token, defaults={"value": value}
            )

        cls.default_status = OrderStatus.objects.create(
            token="2342-default", name="Pendent (test)", is_default=True
        )
        cls.draft_status = OrderStatus.objects.create(
            token="2342-draft", name="Esborrany (test)"
        )
        cls.sent_status = OrderStatus.objects.create(
            token="2342-sent", name="Enviada (test)"
        )
        cls.in_progress_status = OrderStatus.objects.create(
            token="5", name="En Curs (test)"
        )
        cls.validate_status = OrderStatus.objects.create(
            token="2342-validate", name="Per validar (test)"
        )
        cls.completed_status = OrderStatus.objects.create(
            token="2342-completed", name="Tancada (test)"
        )
        cls.cancelled_status = OrderStatus.objects.create(
            token="-1", name="Cancel·lat (test)"
        )

        cls.user = User.objects.create_user("user-2342", "user-2342@example.com", "x")
        cls.user.user_permissions.add(
            Permission.objects.get(
                codename="delete_order",
                content_type=ContentType.objects.get_for_model(Order),
            )
        )

        cls.factory = APIRequestFactory()
        cls.view = OrderViewSet.as_view({"delete": "destroy"})

    @classmethod
    def _order(cls, **fields):
        defaults = {"status": cls.default_status}
        defaults.update(fields)
        return Order.objects.create(**defaults)

    def _delete(self, order):
        request = self.factory.delete(f"/order/{order.pk}/")
        force_authenticate(request, user=self.user)
        return self.view(request, pk=order.pk)

    def test_pending_order_deletes_and_publishes_event(self):
        with patch(
            "order.views.order_view.publish_order_deleted_event"
        ) as publish_mock:
            order = self._order()
            response = self._delete(order)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Order.objects.filter(pk=order.pk).exists())
        publish_mock.assert_called_once_with(order)

    def test_draft_order_deletes_without_reports(self):
        with patch(
            "order.views.order_view.publish_order_deleted_event"
        ) as publish_mock:
            order = self._order(status=self.draft_status)
            response = self._delete(order)

        self.assertEqual(response.status_code, 204)
        publish_mock.assert_called_once_with(order)

    def test_sent_order_still_deletable_until_taken(self):
        # L'ordre despatxada a la GMAO (estat 'Enviada') es pot esborrar mentre
        # cap operari l'hagi colpit: és el cas d'ús del ticket.
        with patch(
            "order.views.order_view.publish_order_deleted_event"
        ) as publish_mock:
            order = self._order(status=self.sent_status)
            response = self._delete(order)

        self.assertEqual(response.status_code, 204)
        publish_mock.assert_called_once_with(order)

    def test_in_progress_order_is_blocked(self):
        order = self._order(status=self.in_progress_status)
        response = self._delete(order)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get("code"), "order_delete_blocked")
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())

    def test_validate_status_order_is_blocked(self):
        # Token del ConfigProject 'for_validate_order_status_token'.
        order = self._order(status=self.validate_status)
        response = self._delete(order)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get("code"), "order_delete_blocked")
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())

    def test_completed_status_order_is_blocked(self):
        # Token del ConfigProject 'order_status_completed_token'.
        order = self._order(status=self.completed_status)
        response = self._delete(order)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get("code"), "order_delete_blocked")
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())

    def test_order_with_reports_is_blocked(self):
        order = self._order()
        OrderReport.objects.create(token="2342-report", order=order)
        response = self._delete(order)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get("code"), "order_delete_blocked")
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())

    def test_completed_at_order_is_blocked(self):
        import datetime

        order = self._order(completed_at=datetime.datetime(2026, 1, 1))
        response = self._delete(order)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get("code"), "order_delete_blocked")
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())

    def test_reported_and_completed_order_is_blocked(self):
        order = self._order(status=self.in_progress_status)
        OrderReport.objects.create(token="2342-report-2", order=order)
        response = self._delete(order)

        self.assertEqual(response.status_code, 400)
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())


class OrderDeletedEventPayloadTestCase(TestCase):
    """Contracte del payload:('order.deleted', {'order_token': ...})."""

    def test_deleted_event_payload_contains_order_token(self):
        status = OrderStatus.objects.create(
            token="2342-payload", name="Payload (test)"
        )
        order = Order.objects.create(token="ORDER-2342", status=status)

        with patch("order.services.rabbit.publish_event") as publish_mock:
            publish_order_deleted_event(order)

        publish_mock.assert_called_once_with(
            "order.deleted", {"order_token": "ORDER-2342"}
        )
