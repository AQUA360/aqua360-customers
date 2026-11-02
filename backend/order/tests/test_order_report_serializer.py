from datetime import time

from django.test import TestCase

from order.models import Order, OrderReport
from order.serializers.order_report_serializer import OrderReportSerializer


class OrderReportTimesTest(TestCase):
    """Les hores d'inici i fi són opcionals, però han d'anar juntes."""

    def setUp(self):
        self.order = Order.objects.create(token="ORD-TEST")

    def _serializer(self, data, instance=None):
        return OrderReportSerializer(instance=instance, data=data, partial=instance is not None)

    def test_without_times_is_valid(self):
        serializer = self._serializer({'order': self.order.id, 'report_date': '2026-01-01', 'title': 'Revisió'})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        report = serializer.save()
        self.assertIsNone(report.time_dedicated)
        self.assertEqual(report.title, 'Revisió')

    def test_only_one_time_is_invalid(self):
        serializer = self._serializer({'order': self.order.id, 'start_at': '10:00'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('end_at', serializer.errors)

    def test_end_before_start_is_invalid(self):
        serializer = self._serializer({'order': self.order.id, 'start_at': '10:00', 'end_at': '09:00'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('end_at', serializer.errors)

    def test_both_times_compute_time_dedicated(self):
        serializer = self._serializer({'order': self.order.id, 'start_at': '10:00', 'end_at': '11:30'})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.save().time_dedicated, 90)

    def test_clearing_times_clears_time_dedicated(self):
        report = OrderReport.objects.create(
            order=self.order, start_at=time(10, 0), end_at=time(11, 0), time_dedicated=60,
        )
        serializer = self._serializer({'start_at': None, 'end_at': None}, instance=report)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.save().time_dedicated)
