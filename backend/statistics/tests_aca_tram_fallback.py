from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from statistics.utils.report_billing_service import _aca_price_to_interval

PART_FIXA = 'part_fixa'
PART_VARIABLE = 'part_variable'


def _line(line_id, price_unit, article_token=PART_VARIABLE):
    article = SimpleNamespace(token=article_token) if article_token else None
    line_item_type = SimpleNamespace(article=article) if article_token else None
    return SimpleNamespace(id=line_id, price_unit=Decimal(price_unit), line_item_type=line_item_type)


class AcaPriceToIntervalTests(SimpleTestCase):
    def test_lowest_price_is_first_tram(self):
        lines = [_line(1, '4.8213'), _line(2, '0.5232'), _line(3, '3.6156'), _line(4, '1.2052')]
        self.assertEqual(
            _aca_price_to_interval(lines, PART_FIXA),
            {Decimal('0.5232'): 1, Decimal('1.2052'): 2, Decimal('3.6156'): 3, Decimal('4.8213'): 4},
        )

    def test_fixed_part_is_not_a_tram(self):
        # Factura sense interval a les línies: la part fixa té un preu entre els dos trams
        lines = [_line(1, '1.2052'), _line(2, '1.0', PART_FIXA), _line(3, '0.5232')]
        self.assertEqual(
            _aca_price_to_interval(lines, PART_FIXA),
            {Decimal('0.5232'): 1, Decimal('1.2052'): 2},
        )

    def test_repeated_prices_share_tram_and_lines_without_type_count(self):
        lines = [_line(1, '0.5232'), _line(2, '0.5232', None), _line(3, '1.2052')]
        self.assertEqual(
            _aca_price_to_interval(lines, PART_FIXA),
            {Decimal('0.5232'): 1, Decimal('1.2052'): 2},
        )
