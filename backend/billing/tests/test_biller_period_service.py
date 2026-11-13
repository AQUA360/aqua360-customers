from datetime import date

from django.test import SimpleTestCase

from billing.utils.biller_period_service import (
    cycle_containing,
    cycle_dates,
    previous_cycle,
)


class _Biller:
    def __init__(self, period_type, initial_month='jan'):
        self.period_type = period_type
        self.initial_month = initial_month


class TestPreviousCycle(SimpleTestCase):
    def _dates(self, target, biller):
        return cycle_dates(previous_cycle(target, biller))

    def test_trimestral_in_november_is_july_september(self):
        self.assertEqual(
            self._dates(date(2026, 11, 13), _Biller('trimestral')),
            (date(2026, 7, 1), date(2026, 9, 30)),
        )

    def test_trimestral_in_january_crosses_year(self):
        self.assertEqual(
            self._dates(date(2027, 1, 10), _Biller('trimestral')),
            (date(2026, 10, 1), date(2026, 12, 31)),
        )

    def test_mensual(self):
        self.assertEqual(
            self._dates(date(2026, 3, 1), _Biller('mensual')),
            (date(2026, 2, 1), date(2026, 2, 28)),
        )
        self.assertEqual(
            self._dates(date(2026, 1, 15), _Biller('mensual')),
            (date(2025, 12, 1), date(2025, 12, 31)),
        )

    def test_semestral(self):
        self.assertEqual(
            self._dates(date(2026, 8, 5), _Biller('semestral')),
            (date(2026, 1, 1), date(2026, 6, 30)),
        )

    def test_initial_month_not_january(self):
        biller = _Biller('trimestral', 'feb')
        # Cicles: feb-abr, mai-jul, ago-oct, nov-gen.
        self.assertEqual(
            self._dates(date(2026, 11, 13), biller),
            (date(2026, 8, 1), date(2026, 10, 31)),
        )
        # Canvi d'any: el cicle anterior a feb-abr 2027 és nov 2026 - gen 2027.
        self.assertEqual(
            self._dates(date(2027, 3, 1), biller),
            (date(2026, 11, 1), date(2027, 1, 31)),
        )

    def test_without_biller_uses_defaults(self):
        self.assertEqual(
            self._dates(date(2026, 11, 13), None),
            (date(2026, 7, 1), date(2026, 9, 30)),
        )

    def test_cycle_dates_of_current_cycle(self):
        cycle = cycle_containing(date(2026, 11, 13), 'trimestral', 'jan')
        self.assertEqual(cycle_dates(cycle), (date(2026, 10, 1), date(2026, 12, 31)))
