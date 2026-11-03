import datetime
from decimal import Decimal
from io import BytesIO

import openpyxl
from django.test import SimpleTestCase

from billing.tests.test_factdeta_baixa import PART_FIXA, line, part_fixa, record
from billing.utils.factdeta_reader import (
    INCIDENCE,
    build_factdeta_workbook,
    read_factdeta,
    summarize_factdeta,
    validate_record,
)
from billing.utils.generate_factdeta_service import (
    build_factdeta_detail_record,
    compute_factdeta_canon,
    round_factdeta_amounts,
)

HEADER = '10' + '2189' + 'A00000000   ' + 'FACTDETA' + '2026' + '080000' + ' ' * 628


def total_line(invoices, records):
    return '30' + '2189' + 'A00000000   ' + '080000' + str(invoices).zfill(8) + str(records).zfill(8) + ' ' * 624


def domestic_record(invoice_number='1000000001', sign=1, **overrides):
    lines = [line(1, sign * 10, 0.5, interval=1), line(2, sign * 5, 1.2, interval=2), part_fixa(3, sign * 3.25)]
    canon = compute_factdeta_canon('D', lines, PART_FIXA)
    round_factdeta_amounts(canon)
    return build_factdeta_detail_record(record('D', canon, invoice_number=invoice_number, **overrides))


def factdeta_file(*details, invoices=None, records=None):
    invoices = len(details) if invoices is None else invoices
    records = len(details) + 2 if records is None else records
    return '\n'.join([HEADER, *details, total_line(invoices, records)]) + '\n'


def messages(factdeta, level=None):
    return [issue['message'] for issue in factdeta.issues if level is None or issue['level'] == level]


class TestFactdetaReaderParsing(SimpleTestCase):
    """El lector desxifra per posicions el que escriu el generador."""

    def test_reads_generated_record(self):
        factdeta = read_factdeta(factdeta_file(domestic_record()).encode(), 'FD2189_080000_2026.txt')
        self.assertEqual(len(factdeta.records), 1)
        parsed = factdeta.records[0]
        self.assertEqual(parsed['invoice'], '1000000001')
        self.assertEqual(parsed['tariff'], 'D')
        self.assertEqual(parsed['issue_date'], datetime.date(2026, 3, 1))
        self.assertEqual((parsed['t1_volume'], parsed['t1_rate'], parsed['t1_amount']), (10, Decimal('0.5'), 5))
        self.assertEqual((parsed['t2_volume'], parsed['t2_amount']), (5, 6))
        self.assertEqual(parsed['billed_volume'], 15)
        self.assertEqual(
            (parsed['variable_amount'], parsed['fixed_amount'], parsed['total_amount']),
            (Decimal('11'), Decimal('3.25'), Decimal('14.25')),
        )
        self.assertEqual(factdeta.incidences, [])

    def test_negative_amounts(self):
        detail = domestic_record(sign=-1, cancelled_number='1000000000', cancelled_date=datetime.date(2026, 2, 1))
        parsed = read_factdeta(factdeta_file(detail)).records[0]
        self.assertEqual(parsed['total_amount'], Decimal('-14.25'))
        self.assertEqual(parsed['t1_volume'], -10)


class TestFactdetaReaderFileChecks(SimpleTestCase):

    def test_total_record_counts_must_match(self):
        factdeta = read_factdeta(factdeta_file(domestic_record(), invoices=2, records=5))
        self.assertIn("el total declara 2 factures i n'hi ha 1", messages(factdeta, INCIDENCE))
        self.assertIn("el total declara 5 registres i n'hi ha 3", messages(factdeta, INCIDENCE))

    def test_wrong_line_length(self):
        factdeta = read_factdeta(factdeta_file(domestic_record()[:-1]))
        self.assertTrue(any('663 caràcters' in message for message in messages(factdeta, INCIDENCE)))

    def test_repeated_invoice(self):
        factdeta = read_factdeta(factdeta_file(domestic_record(), domestic_record()))
        self.assertTrue(any('factura repetida' in message for message in messages(factdeta, INCIDENCE)))

    def test_file_name_must_match_header(self):
        factdeta = read_factdeta(factdeta_file(domestic_record()), 'FD2189_080001_2026.txt')
        self.assertTrue(any('nom del fitxer' in message for message in messages(factdeta, INCIDENCE)))


class TestFactdetaReaderRecordChecks(SimpleTestCase):

    def parsed(self, **overrides):
        return read_factdeta(factdeta_file(domestic_record(**overrides))).records[0]

    def test_total_must_be_variable_plus_fixed(self):
        parsed = self.parsed()
        parsed['fixed_amount'] += Decimal('0.01')
        self.assertIn((INCIDENCE, "l'import total no és la part variable més la fixa"), validate_record(parsed))

    def test_consumption_only_tariff_with_amounts(self):
        parsed = self.parsed()
        parsed['tariff'] = 'X'
        self.assertTrue(any(level == INCIDENCE and message.startswith('tarifa X amb camps que han de ser zero')
                            for level, message in validate_record(parsed)))

    def test_negative_total_needs_cancelled_invoice(self):
        parsed = read_factdeta(factdeta_file(domestic_record(sign=-1))).records[0]
        self.assertIn((INCIDENCE, "import negatiu sense factura anul·lada"), validate_record(parsed))

    def test_tram_volumes_must_add_up(self):
        parsed = self.parsed()
        parsed['billed_volume'] += 1
        self.assertIn(
            (INCIDENCE, "la suma de trams, bo social i fuites no coincideix amb el volum facturat"),
            validate_record(parsed),
        )


class TestFactdetaReaderSummary(SimpleTestCase):

    def test_totals_by_tariff_and_sign(self):
        refund = domestic_record('1000000002', sign=-1, cancelled_number='1000000001',
                                 cancelled_date=datetime.date(2026, 3, 1))
        factdeta = read_factdeta(factdeta_file(domestic_record(), refund))
        summary = summarize_factdeta(factdeta)
        self.assertEqual(summary['total']['count'], 2)
        self.assertEqual(summary['total']['total_amount'], 0)
        self.assertEqual(summary['by_sign']['Factures']['total_amount'], Decimal('14.25'))
        self.assertEqual(summary['by_sign']['Abonaments (total negatiu)']['variable_amount'], Decimal('-11'))
        self.assertEqual(summary['by_tariff']['D']['count'], 2)

    def test_workbook_has_summary_records_and_validations(self):
        factdeta = read_factdeta(factdeta_file(domestic_record()), 'FD2189_080000_2026.txt')
        buffer = BytesIO()
        build_factdeta_workbook(factdeta).save(buffer)
        workbook = openpyxl.load_workbook(BytesIO(buffer.getvalue()))
        self.assertEqual(workbook.sheetnames, ['Resum', 'Registres', 'Validacions'])
        self.assertEqual(workbook['Registres'].max_row, 2)
        totals = {row[0]: row[2] for row in workbook['Resum'].iter_rows(values_only=True) if row and row[0]}
        self.assertEqual(totals['Import total cànon'], 14.25)
