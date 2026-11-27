"""Esdeveniment order.status.changed cap al GMAO (#2936): contingut del missatge."""
from unittest.mock import patch

from django.test import TestCase

from order.models import OrderStatus
from order.services.rabbit import publish_order_status_changed


class OrderStatusChangedEventTest(TestCase):
    def test_payload(self):
        status = OrderStatus(token='1', name='Pendent')
        previous = OrderStatus(token='5', name='En Curs')

        with patch('order.services.consumer.GMAO_STATUS_MAPPING', {'pending': '1', 'in_progress': '5'}), \
                patch('order.services.rabbit.publish_event') as publish_event:
            publish_order_status_changed('ORD-1', status, previous, 'Canvi automàtic per la baixa BX-1')

        publish_event.assert_called_once_with('order.status.changed', {
            'order_token': 'ORD-1',
            'status_token': '1',
            'status_name': 'Pendent',
            'gmao_status': 'pending',
            'previous_status_token': '5',
            'previous_status_name': 'En Curs',
            'reason': 'Canvi automàtic per la baixa BX-1',
        })
