from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from billing.models import Billing, BillingStatus
from coredata.models import ConfigProject


class BillingPeriodEditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.open_status = BillingStatus.objects.create(token='period-open')
        cls.locked_statuses = []
        for key, value in (
            ('billing_batch_processing_documents', 'period-documents'),
            ('billing_batch_processed', 'period-processed'),
        ):
            ConfigProject.objects.update_or_create(token=key, defaults={'value': value})
            cls.locked_statuses.append(BillingStatus.objects.create(token=value))
        cls.billing = Billing.objects.create(
            name='Facturació', status=cls.open_status,
            period_start=date(2026, 1, 1), period_end=date(2026, 3, 31),
        )
        cls.user = get_user_model().objects.create_superuser('period-admin', 'period@example.com', 'x')

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = f'/billing/billing/{self.billing.pk}/'

    def test_locked_statuses_reject_changes_to_each_date(self):
        for status in self.locked_statuses:
            Billing.objects.filter(pk=self.billing.pk).update(status=status)
            for field, value in (('period_start', '2026-02-01'), ('period_end', None)):
                with self.subTest(status=status.token, field=field):
                    response = self.client.patch(self.url, {field: value}, format='json')
                    self.assertEqual(response.status_code, 400, response.data)
                    self.assertIn(field, response.data)
                    self.billing.refresh_from_db()
                    self.assertEqual(self.billing.period_start, date(2026, 1, 1))
                    self.assertEqual(self.billing.period_end, date(2026, 3, 31))

    def test_locked_billing_allows_unchanged_dates_and_other_edits(self):
        Billing.objects.filter(pk=self.billing.pk).update(status=self.locked_statuses[0])
        response = self.client.put(self.url, {
            'name': 'Nou nom', 'period_start': '2026-01-01', 'period_end': '2026-03-31',
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.billing.refresh_from_db()
        self.assertEqual(self.billing.name, 'Nou nom')

    def test_open_billing_accepts_valid_change_and_rejects_reversed_dates(self):
        response = self.client.patch(self.url, {'period_start': '2026-02-01'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        response = self.client.patch(self.url, {'period_end': '2026-01-01'}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('period_end', response.data)
        self.billing.refresh_from_db()
        self.assertEqual(self.billing.period_start, date(2026, 2, 1))
        self.assertEqual(self.billing.period_end, date(2026, 3, 31))

    def test_missing_status_does_not_match_empty_configuration(self):
        ConfigProject.objects.filter(token='billing_batch_processed').update(value=None)
        Billing.objects.filter(pk=self.billing.pk).update(status=None)
        response = self.client.patch(self.url, {'period_start': '2026-02-01'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
