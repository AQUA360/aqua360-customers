import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from billing.models import Biller, Billing, BillingStatus
from billing.views.billing_view import StartBillingView


class TestStartBillingPeriod(TestCase):
    """`StartBillingView` desa el període triat o, per defecte, l'últim cicle tancat."""

    @classmethod
    def setUpTestData(cls):
        BillingStatus.objects.update_or_create(
            token='start-period-default', defaults={'name': 'Oberta', 'is_default': True}
        )
        cls.biller = Biller.objects.create(
            token='biller-start-period', name='Biller', period_type='trimestral'
        )
        cls.user = get_user_model().objects.create_superuser(
            username='start-period', password='x', email=''
        )

    def _start(self, params=None):
        params = {'biller_id': self.biller.id, **(params or {})}
        request = APIRequestFactory().get('/billing/start/', params)
        force_authenticate(request, user=self.user)
        with mock.patch(
            'billing.views.billing_view.timezone.localdate',
            return_value=datetime.date(2026, 11, 13),
        ):
            return StartBillingView.as_view(http_method_names=['get'])(request)

    def test_explicit_period(self):
        response = self._start({'period_start': '2026-10-01', 'period_end': '2026-12-31'})

        self.assertEqual(response.status_code, 200, response.data)
        billing = Billing.objects.get(id=response.data['id'])
        self.assertEqual(billing.period_start, datetime.date(2026, 10, 1))
        self.assertEqual(billing.period_end, datetime.date(2026, 12, 31))

    def test_default_period_is_previous_cycle(self):
        response = self._start()

        self.assertEqual(response.status_code, 200, response.data)
        billing = Billing.objects.get(id=response.data['id'])
        self.assertEqual(billing.period_start, datetime.date(2026, 7, 1))
        self.assertEqual(billing.period_end, datetime.date(2026, 9, 30))

    def test_start_after_end_is_rejected(self):
        response = self._start({'period_start': '2026-12-31', 'period_end': '2026-10-01'})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Billing.objects.exists())

    def test_invalid_date_is_rejected(self):
        response = self._start({'period_start': 'xx', 'period_end': '2026-10-01'})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Billing.objects.exists())
