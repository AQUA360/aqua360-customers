from django.test import SimpleTestCase

from coredata.utils.phone_utils import is_mobile_phone, normalize_phone, to_broadcaster_format


class PhoneUtilsTests(SimpleTestCase):
    """Només els mòbils poden rebre SMS: els fixos s'han de descartar."""

    def test_spanish_mobiles(self):
        for phone in ('612345678', '712345678', '+34 612 345 678', '0034612345678', '612-34-56-78', '(+34) 612.345.678'):
            self.assertTrue(is_mobile_phone(phone), phone)

    def test_spanish_landlines_and_special_numbers(self):
        for phone in ('972123456', '+34 934 567 890', '0034934567890', '812345678', '900123456', '702345678'):
            self.assertFalse(is_mobile_phone(phone), phone)

    def test_malformed_or_empty(self):
        for phone in (None, '', '   ', 'sense telèfon', '61234567', '6123456789'):
            self.assertFalse(is_mobile_phone(phone), phone)

    def test_foreign_numbers_are_accepted(self):
        # D'un número estranger no se sap si és fix: es dona per bo si té una llargada vàlida.
        self.assertTrue(is_mobile_phone('+33 6 12 34 56 78'))
        self.assertTrue(is_mobile_phone('0044 7911 123456'))
        self.assertFalse(is_mobile_phone('+33 123'))

    def test_normalize_phone(self):
        self.assertEqual(normalize_phone(' 612 34-56.78 '), '612345678')
        self.assertEqual(normalize_phone('0034 612345678'), '+34612345678')
        self.assertEqual(normalize_phone('+34 612345678'), '+34612345678')
        self.assertEqual(normalize_phone(None), '')

    def test_to_broadcaster_format(self):
        # Broadcaster vol el prefix de país sense '+', com a Aqua360 Sign.
        self.assertEqual(to_broadcaster_format('612 34 56 78'), '34612345678')
        self.assertEqual(to_broadcaster_format('+34 612345678'), '34612345678')
        self.assertEqual(to_broadcaster_format('0033 6 12 34 56 78'), '33612345678')
        self.assertEqual(to_broadcaster_format('972123456'), '')
        self.assertEqual(to_broadcaster_format(None), '')
