from django.test import SimpleTestCase

from contract.utils.aca_bonification_export_service import n, x
from contract.utils.aca_exchange_file_parser import (
    ACAExchangeFileError, details_to_changes, looks_like_exchange_file, parse_exchange_file,
)


def _header(application='CS'):
    return x('10', 2) + n('598', 4) + x('A00000000', 20) + x('20240321', 8) + x(application, 2) + x('', 314)


def _detail(num_persons='90', result='01', policy='1865', report=''):
    return (
        x('20', 2) + x('E', 1) + x('20231219', 8) + x('COGNOM', 25) + x('SEGON', 25) + x('NOM', 20)
        + x('1', 1) + x('00000000T', 20) + x('CR', 2) + x('MAJOR', 50) + x('2', 4) + x('', 1)
        + x('', 2) + x('A', 2) + x('1R', 3) + x('4A', 4) + x('8310', 5) + n('080095', 6)
        + x('', 10) + x('', 10) + x('', 100) + x(num_persons, 2) + n('598', 4) + x(policy, 15)
        + x('S', 1) + x(result, 2) + x('1', 1) + n('0', 2) + x(report, 22)
    )


def _total(requests):
    return x('30', 2) + n('598', 4) + x('A00000000', 20) + n(requests, 8) + n(requests + 2, 8) + x('', 308)


def _file(*details, application='CS'):
    lines = [_header(application), *details, _total(len(details))]
    return '\r\n'.join(lines).encode('cp1252') + b'\r\n'


class ACAExchangeFileParserTest(SimpleTestCase):
    def test_parses_canon_social_file(self):
        raw = _file(_detail(), _detail(policy='7769'))
        self.assertTrue(looks_like_exchange_file(raw))

        parsed = parse_exchange_file(raw)
        self.assertEqual(parsed['header']['application'], 'CS')
        self.assertEqual(parsed['header']['supplier_code'], '0598')

        changes = details_to_changes(parsed['details'], 'CS')
        self.assertEqual([c['contract_code'] for c in changes], ['1865', '7769'])
        self.assertEqual(changes[0]['social_collective'], '90')
        self.assertEqual(changes[0]['num_persons'], '')
        first = changes[0]
        self.assertEqual(first['person_name'], 'COGNOM SEGON NOM')
        self.assertEqual(first['postal_code'], '08310')
        self.assertEqual(first['address'], 'CR MAJOR 2 A 1R 4A')
        self.assertEqual(str(first['request_date']), '2023-12-19')
        self.assertTrue(first['accepted'])
        self.assertFalse(first['closing'])

    def test_closing_and_rejected_lines(self):
        changes = details_to_changes(parse_exchange_file(
            _file(_detail(num_persons='TA', result=''), _detail(num_persons='02', result='06'), application='AT')
        )['details'], 'AT')
        self.assertTrue(changes[0]['closing'])
        self.assertTrue(changes[0]['accepted'])
        self.assertFalse(changes[1]['closing'])
        self.assertFalse(changes[1]['accepted'])

    def test_social_collective_report_and_closing_code_23(self):
        changes = details_to_changes(parse_exchange_file(
            _file(_detail(num_persons='92', report='0598_20240321_01'), _detail(num_persons='AT', result='23'))
        )['details'], 'CS')
        self.assertEqual(changes[0]['social_collective'], '92')
        self.assertEqual(changes[0]['collective_report'], '0598_20240321_01')
        self.assertTrue(changes[1]['closing'])

    def test_ampliacio_trams_keeps_num_persons(self):
        changes = details_to_changes(parse_exchange_file(_file(_detail(num_persons='05'), application='AT'))['details'], 'AT')
        self.assertEqual(changes[0]['num_persons'], '05')
        self.assertEqual(changes[0]['social_collective'], '')

    def test_total_mismatch_is_rejected(self):
        raw = '\r\n'.join([_header(), _detail(), _total(3)]).encode('cp1252')
        with self.assertRaises(ACAExchangeFileError):
            parse_exchange_file(raw)

    def test_html_table_is_not_an_exchange_file(self):
        self.assertFalse(looks_like_exchange_file(b'<table><tr><td>ABONAT</td></tr></table>'))
