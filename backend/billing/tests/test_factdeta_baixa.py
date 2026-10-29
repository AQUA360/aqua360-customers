import datetime
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from billing.utils.generate_factdeta_service import (
    FACTDETA_LINE_LENGTH,
    FactdetaValidationError,
    _customer_id,
    _num,
    build_factdeta_detail_record,
    compute_factdeta_canon,
    factdeta_record_warnings,
    get_factdeta_tariff_type,
    latlon_to_utm31,
)

PART_FIXA = 'part_fixa'
# Posicions (0-based) dels imports finals del registre 20 segons el document 03 de l'ACA
VARIABLE_AMOUNT = slice(565, 579)
FIXED_AMOUNT = slice(579, 592)
TOTAL_AMOUNT = slice(592, 606)


def line(id, units, price_unit, name='PART VARIABLE', interval=0, article=None, quantity='consum', price=None):
    return SimpleNamespace(
        id=id,
        units=Decimal(str(units)),
        price_unit=Decimal(str(price_unit)),
        price=Decimal(str(price if price is not None else Decimal(str(units)) * Decimal(str(price_unit)))),
        interval=interval,
        name=name,
        line_item_type=SimpleNamespace(
            name=name,
            article=SimpleNamespace(token=article) if article else None,
            quantity=SimpleNamespace(token=quantity) if quantity else None,
        ),
    )


def part_fixa(id, price):
    return line(id, 1, price, name='PART FIXA', article=PART_FIXA, quantity=None)


def record(tariff_type, canon, **overrides):
    data = {
        'ine_code': '080000', 'invoice_number': '1000000001', 'issue_date': datetime.date(2026, 3, 1),
        'customer_id': '00000000T', 'tariff_type': tariff_type, 'surname1': 'COGNOM', 'surname2': '',
        'name': 'NOM', 'street_code': 'CR', 'street_name': 'CARRER', 'street_number': '1', 'floor': '',
        'door': '', 'stair': '', 'postal_code': '08000', 'city': 'POBLACIO', 'policy': '000001',
        'meter': 'M1', 'billing_system': 'C', 'period_start': datetime.date(2026, 1, 1),
        'period_end': datetime.date(2026, 2, 28), 'consumed_volume': canon['billed_volume'], 'canon': canon,
        'cancelled_number': '', 'cancelled_date': None, 'alternative_network': '', 'tram_extension': 'N',
        'inhabitants': 0, 'social_tariff': 'N', 'vulnerable': 'N', 'establishment_code': '', 'homes': 0,
        'places': 0, 'utm_x': 430000, 'utm_y': 4580000,
    }
    data.update(overrides)
    return data


class TestFactdetaNumericFields(SimpleTestCase):
    """Camps numèrics del document 03: zeros a l'esquerra, decimals implícits i signe al primer dígit."""

    def test_integer_is_zero_padded(self):
        self.assertEqual(_num(34, 9), '000000034')

    def test_negative_sign_goes_in_first_digit(self):
        self.assertEqual(_num(-34270, 9), '-00034270')

    def test_decimals_are_implicit(self):
        self.assertEqual(_num(Decimal('9325.46'), 6, 4), '0093254600')
        self.assertEqual(_num(9325, 6, 4), '0093250000')

    def test_value_too_long_raises(self):
        with self.assertRaises(FactdetaValidationError):
            _num(1000, 3)


class TestFactdetaCustomerId(SimpleTestCase):

    def test_separators_are_removed(self):
        self.assertEqual(_customer_id('00000000-t'), '00000000T')
        self.assertEqual(_customer_id(' X 0000000 T '), 'X0000000T')

    def test_dni_is_zero_padded(self):
        self.assertEqual(_customer_id('0000000T'), '00000000T')


class TestFactdetaTariffType(SimpleTestCase):

    def test_fire_use_is_fire_extinction(self):
        self.assertEqual(get_factdeta_tariff_type('D', [line(1, 10, 0.5, interval=1)], is_fire=True), 'X')

    def test_industrial_without_price_is_exempt(self):
        self.assertEqual(get_factdeta_tariff_type('I', [line(1, 10, 0, name="CANON D'US INDUSTRIAL GENERAL")]), 'E')

    def test_domestic_contract_with_industrial_lines_is_industrial(self):
        lines = [line(1, 10, 0.5, name="PART VARIABLE ÚS INDUSTRIAL GENERAL")]
        self.assertEqual(get_factdeta_tariff_type('D', lines), 'I')

    def test_industrial_contract_with_domestic_trams_is_domestic(self):
        self.assertEqual(get_factdeta_tariff_type('I', [line(1, 10, 0.5, interval=1)]), 'D')

    def test_new_tariff_types_are_kept(self):
        self.assertEqual(get_factdeta_tariff_type('G', [line(1, 10, 0)]), 'G')

    def test_without_use_aca_guesses_from_intervals(self):
        self.assertEqual(get_factdeta_tariff_type(None, [line(1, 10, 0.5, interval=1)]), 'D')
        self.assertEqual(get_factdeta_tariff_type(None, [line(1, 10, 0.5)]), 'I')


class TestFactdetaDomesticRecord(SimpleTestCase):

    def test_trams_social_leak_and_part_fixa(self):
        lines = [
            line(1, 10, 0.5, interval=1),
            line(2, 5, 1.2, interval=2),
            line(3, 4, 0, interval=1),                                   # bo social: tarifa 0
            line(4, 3, 0.5, name='CONSUM FUITA', quantity='diferencia_fuita'),
            part_fixa(5, 3.25),
        ]
        canon = compute_factdeta_canon('D', lines, PART_FIXA)

        self.assertEqual(canon['billed_volume'], 22)
        self.assertEqual(canon['trams'][0], (Decimal('10'), Decimal('0.5'), Decimal('5.0')))
        self.assertEqual(canon['trams'][1], (Decimal('5'), Decimal('1.2'), Decimal('6.0')))
        self.assertEqual(canon['social'][0], 4)
        self.assertEqual(canon['leak'][0], 3)
        self.assertEqual(canon['fixed_amount'], Decimal('3.25'))
        self.assertEqual(canon['variable_amount'], Decimal('12.5'))

        data = record('D', canon, social_tariff='S')
        detail = build_factdeta_detail_record(data)
        self.assertEqual(len(detail), FACTDETA_LINE_LENGTH)
        self.assertEqual(detail[VARIABLE_AMOUNT], '00000000001250')
        self.assertEqual(detail[FIXED_AMOUNT], '0000000000325')
        self.assertEqual(detail[TOTAL_AMOUNT], '00000000001575')
        self.assertEqual(factdeta_record_warnings(data), [])

    def test_lines_without_interval_are_ordered_by_price(self):
        canon = compute_factdeta_canon('D', [line(1, 10, 1.2), line(2, 10, 0.5)], PART_FIXA)
        self.assertEqual(canon['trams'][0][1], Decimal('0.5'))
        self.assertEqual(canon['trams'][1][1], Decimal('1.2'))
        self.assertFalse(canon['unclassified_trams'])

    def test_lines_without_interval_skip_known_trams_and_are_warned(self):
        canon = compute_factdeta_canon('D', [line(1, 10, 0.5, interval=1), line(2, 5, 1.2)], PART_FIXA)
        self.assertEqual(canon['trams'][0], (Decimal('10'), Decimal('0.5'), Decimal('5.0')))
        self.assertEqual(canon['trams'][1], (Decimal('5'), Decimal('1.2'), Decimal('6.0')))
        self.assertIn("línies de cànon sense tram assignat: revisar el tram declarat", factdeta_record_warnings(record('D', canon)))

    def test_refund_is_negative_and_needs_cancelled_invoice(self):
        canon = compute_factdeta_canon('D', [line(1, -10, 0.5, interval=1), part_fixa(2, -3.25)], PART_FIXA)
        data = record('D', canon)
        detail = build_factdeta_detail_record(data)
        self.assertEqual(detail[TOTAL_AMOUNT], '-0000000000825')
        self.assertIn("import negatiu sense factura anul·lada", factdeta_record_warnings(data))

        data = record('D', canon, cancelled_number='1000000000', cancelled_date=datetime.date(2026, 2, 1))
        self.assertNotIn("import negatiu sense factura anul·lada", factdeta_record_warnings(data))

    def test_missing_part_fixa_is_warned(self):
        canon = compute_factdeta_canon('D', [line(1, 10, 0.5, interval=1)], PART_FIXA)
        self.assertIn("sense import de part fixa", factdeta_record_warnings(record('D', canon)))


class TestFactdetaIndustrialRecord(SimpleTestCase):

    def test_general_includes_leak_and_specific_only_consumption(self):
        lines = [
            line(1, 12, 0.5, name="PART VARIABLE ÚS INDUSTRIAL GENERAL", quantity='diferencia_fuita_consum'),
            line(2, 10, 0.25, name="PART VARIABLE ÚS INDUSTRIAL ESPECÍFIC"),
            line(3, 2, 0.125, name="CONSUM FUITA", quantity='diferencia_fuita'),
            part_fixa(4, 10),
        ]
        canon = compute_factdeta_canon('I', lines, PART_FIXA)

        general_volume, general_rate, general_amount = canon['general']
        specific_volume, _specific_rate, specific_amount = canon['specific']
        leak_volume, leak_rate, leak_amount = canon['leak']
        # Validacions del document 08: el general és el volum facturat total i l'específic més
        # la fuita també hi han de sumar
        self.assertEqual(canon['billed_volume'], 12)
        self.assertEqual(general_volume, canon['billed_volume'])
        self.assertEqual(specific_volume + leak_volume, canon['billed_volume'])
        self.assertEqual(general_amount, general_volume * general_rate)
        self.assertEqual(leak_rate, Decimal('0.125'))
        self.assertEqual(general_amount + specific_amount + leak_amount, canon['variable_amount'])
        self.assertEqual(len(build_factdeta_detail_record(record('I', canon))), FACTDETA_LINE_LENGTH)

    def test_municipal_only_has_general_tariff(self):
        lines = [line(1, 8, 0.5, name="PART VARIABLE ÚS INDUSTRIAL GENERAL"), part_fixa(2, 5)]
        canon = compute_factdeta_canon('A', lines, PART_FIXA)
        self.assertEqual(canon['general'][0], 8)
        self.assertEqual(canon['specific'], (0, 0, 0))
        self.assertEqual(canon['leak'], (0, 0, 0))

    def test_exempt_only_declares_consumption(self):
        canon = compute_factdeta_canon('E', [line(1, 8, 0), part_fixa(2, 5)], PART_FIXA)
        self.assertEqual(canon['billed_volume'], 0)
        self.assertEqual(canon['fixed_amount'], 0)


class TestLatLonToUtm31(SimpleTestCase):

    def test_central_meridian(self):
        x, y = latlon_to_utm31(41, 3)
        self.assertEqual(x, 500000)
        # Arc de meridià a 41º integrat numèricament (WGS84) per k0
        self.assertAlmostEqual(y, 4538757.06, delta=0.05)

    def test_symmetric_around_central_meridian(self):
        west_x, west_y = latlon_to_utm31(41.5, 2)
        east_x, east_y = latlon_to_utm31(41.5, 4)
        self.assertAlmostEqual(west_x + east_x, 1000000, delta=0.02)
        self.assertAlmostEqual(west_y, east_y, delta=0.02)
