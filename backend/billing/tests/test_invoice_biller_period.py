from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from billing.templatetags.billing_filters import invoice_biller_period


def _reading(reading_date, previous_date=None):
    previous = SimpleNamespace(reading_date=previous_date) if previous_date else None
    return SimpleNamespace(
        reading_date=reading_date,
        previous_reading=previous,
        previous_reading_id=1 if previous else None,
    )


def _invoice(readings=(), year=None, month=None, period_type='trimestral', initial_month='jan'):
    return SimpleNamespace(
        origin=SimpleNamespace(token='aigua'),
        billing=SimpleNamespace(
            biller=SimpleNamespace(period_type=period_type, initial_month=initial_month)
        ),
        readings=SimpleNamespace(all=lambda: list(readings)),
        billing_period_year=year,
        billing_period_month=month,
    )


@patch('billing.templatetags.billing_filters.get_config', return_value='aigua')
class InvoiceBillerPeriodTests(SimpleTestCase):

    def test_issued_next_quarter_uses_readings_period(self, _config):
        # Emesa a l'octubre (mes de període 10) amb lectures de juny a setembre.
        invoice = _invoice(
            [_reading(date(2026, 9, 16), date(2026, 6, 15))], year=2026, month=10,
        )
        self.assertEqual(invoice_biller_period(invoice), 'Juliol-Setembre/2026')

    def test_reading_taken_early_next_quarter_stays_in_its_quarter(self, _config):
        invoice = _invoice([_reading(date(2026, 10, 2), date(2026, 7, 1))])
        self.assertEqual(invoice_biller_period(invoice), 'Juliol-Setembre/2026')

    def test_late_reading_across_year_end(self, _config):
        invoice = _invoice([_reading(date(2027, 1, 5), date(2026, 10, 5))])
        self.assertEqual(invoice_biller_period(invoice), 'Octubre-Desembre/2026')

    def test_very_old_previous_reading_is_limited_to_one_cycle(self, _config):
        # Comptador sense llegir durant anys: no ha de sortir un trimestre antic.
        invoice = _invoice([_reading(date(2025, 12, 12), date(2022, 9, 14))])
        self.assertEqual(invoice_biller_period(invoice), 'Octubre-Desembre/2025')

    def test_without_previous_reading_uses_last_reading_date(self, _config):
        invoice = _invoice([_reading(date(2026, 9, 10))], year=2026, month=10)
        self.assertEqual(invoice_biller_period(invoice), 'Juliol-Setembre/2026')

    def test_meter_change_uses_whole_reading_range(self, _config):
        invoice = _invoice([
            _reading(date(2026, 8, 1), date(2026, 6, 20)),
            _reading(date(2026, 9, 20), date(2026, 8, 1)),
        ])
        self.assertEqual(invoice_biller_period(invoice), 'Juliol-Setembre/2026')

    def test_without_readings_falls_back_to_billing_period(self, _config):
        invoice = _invoice([], year=2026, month=5)
        self.assertEqual(invoice_biller_period(invoice), 'Abril-Juny/2026')

    def test_monthly_biller(self, _config):
        invoice = _invoice(
            [_reading(date(2026, 5, 31), date(2026, 5, 1))], period_type='mensual',
        )
        self.assertEqual(invoice_biller_period(invoice), 'Maig/2026')

    def test_without_readings_nor_period_is_empty(self, _config):
        self.assertEqual(invoice_biller_period(_invoice([])), '')
