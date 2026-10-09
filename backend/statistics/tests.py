from django.test import SimpleTestCase, TestCase

from coredata.models import ConfigProject
from service.models import Exploitation
from service.serializers.exploitation_serializer import ExploitationSerializer
from statistics.utils.incasol import resolve_incasol_num

from statistics.utils.report_billing_by_zone_service import (
    classify_line,
    merge_all_zones,
    _canon_tram_row_label,
    _canon_type_from_rate,
    _invoice_column_meta,
    _padron_column_label,
    _tram_from_name,
    _tram_row_label,
)


class ClassifyLineTests(SimpleTestCase):
    def test_quota_servei(self):
        kind, tram = classify_line(
            '1000', 'Quota de Servei', 'aigua', 'Quota servei', 'Quota fixa',
            None, None, None,
        )
        self.assertEqual(kind, 'quota')
        self.assertIsNone(tram)

    def test_water_tram_from_interval(self):
        kind, tram = classify_line(
            '1001', 'Aigua', 'aigua', 'CONSUM - 2N TRAM; Límit: 84', 'Consum',
            2, 'm3', None,
        )
        self.assertEqual(kind, 'tram')
        self.assertEqual(tram, 2)

    def test_water_tram_from_name_when_interval_missing(self):
        kind, tram = classify_line(
            None, 'Aigua potable', 'aigua', 'Aigua Potable Bloc 3', None,
            None, 'm3', None,
        )
        self.assertEqual(kind, 'tram')
        self.assertEqual(tram, 3)

    def test_sewer(self):
        kind, tram = classify_line(
            'CLV', 'Clavegueram', None, 'Taxa clavegueram', None,
            None, 'm3', None,
        )
        self.assertEqual(kind, 'sewer')
        self.assertIsNone(tram)

    def test_part_fixa_sense_consum_is_quota(self):
        kind, tram = classify_line(
            '1000', 'Aigua', 'aigua', 'PART FIXA (SENSE CONSUM)', 'Part fixa',
            None, None, None,
        )
        self.assertEqual(kind, 'quota')
        self.assertIsNone(tram)

    def test_aca_is_canon_tram(self):
        kind, tram = classify_line(
            'ACA', 'Cànon Aigua (ACA)', 'aigua', 'Part variable 1r tram', None,
            1, 'm3', None,
        )
        self.assertEqual(kind, 'canon')
        self.assertEqual(tram, 1)

    def test_canon_part_fixa_is_quota(self):
        kind, tram = classify_line(
            '1002', 'CÀNON AIGUA (ACA)', 'aigua', 'PART FIXA', 'Part fixa',
            0, None, None,
        )
        self.assertEqual(kind, 'canon_quota')
        self.assertIsNone(tram)


class TramFromNameTests(SimpleTestCase):
    def test_ordinal_tram(self):
        self.assertEqual(_tram_from_name('CONSUM - 1R TRAM'), 1)
        self.assertEqual(_tram_from_name('PART VARIABLE - 4T TRAM (335 m3)'), 4)

    def test_bloc(self):
        self.assertEqual(_tram_from_name('Aigua Potable Bloc 2 (de 36 a 84 m3)'), 2)


class TramLabelTests(SimpleTestCase):
    def test_numbered_tram_has_stable_label(self):
        self.assertEqual(_tram_row_label(1), "CONSUM D'AIGUA - TRAM 1")
        self.assertEqual(_tram_row_label(4), "CONSUM D'AIGUA - TRAM 4")

    def test_does_not_use_m3_limits_or_line_name(self):
        self.assertEqual(
            _tram_row_label(2, {1: 36, 2: 84}, {2: 'CONSUM D\'AIGUA - 36 (0 m3)'}),
            "CONSUM D'AIGUA - TRAM 2",
        )

    def test_sense_tram(self):
        self.assertEqual(_tram_row_label(0), 'Consum aigua (sense tram)')


class ReportTramsTests(SimpleTestCase):
    def test_always_includes_trams_1_to_4(self):
        from statistics.utils.report_billing_by_zone_service import _report_trams
        self.assertEqual(_report_trams([]), [1, 2, 3, 4])
        self.assertEqual(_report_trams([2]), [1, 2, 3, 4])

    def test_keeps_sense_tram_and_extra_trams(self):
        from statistics.utils.report_billing_by_zone_service import _report_trams
        self.assertEqual(_report_trams([0, 5]), [0, 1, 2, 3, 4, 5])


class MergeZonesTests(SimpleTestCase):
    def test_includes_catalog_invoice_and_meter_zones(self):
        catalog = {
            1: {'id': 1, 'name': 'Zona 1', 'position': 1},
            2: {'id': 2, 'name': 'Zona 2', 'position': 2},
        }
        invoice_zones = {0: {'id': 0, 'name': 'Sense zona', 'position': 9999}}
        meters = [{'id': 3, 'name': 'Zona 3'}]
        merged = merge_all_zones(invoice_zones, meters, catalog=catalog)
        self.assertEqual(set(merged), {0, 1, 2, 3})
        self.assertEqual(merged[1]['name'], 'Zona 1')
        self.assertEqual(merged[3]['name'], 'Zona 3')


class CanonTypeTests(SimpleTestCase):
    def test_tokens(self):
        class Rate:
            def __init__(self, token, name=None):
                self.token = token
                self.name = name

        self.assertEqual(_canon_type_from_rate(Rate('CANON-DOM')), 'CANON-DOM')
        self.assertEqual(_canon_type_from_rate(Rate('CANON-MUN')), 'CANON-MUN')
        self.assertEqual(_canon_type_from_rate(Rate('CANON-HOTELS')), 'CANON-HOTELS')
        self.assertEqual(_canon_type_from_rate(Rate('CANON-IND')), 'CANON-IND')
        self.assertEqual(_canon_type_from_rate(Rate(None, 'CAMPINGS I HOTELS')), 'CANON-HOTELS')

    def test_tram_labels(self):
        self.assertEqual(_canon_tram_row_label('CANON-DOM', 1), 'CANON-DOM - TRAM 1')
        self.assertEqual(_canon_tram_row_label('CANON-IND', 0), 'CANON-IND (sense tram)')


class InvoiceColumnMetaTests(SimpleTestCase):
    def _invoice(self, **kwargs):
        class Class:
            def __init__(self, token):
                self.token = token

        class Billing:
            def __init__(self, id, name):
                self.id = id
                self.name = name
                self.created_at = None

        inv = type('Inv', (), {})()
        inv.invoice_class_id = kwargs.get('invoice_class_id')
        inv.invoice_class = Class(kwargs['class_token']) if kwargs.get('class_token') else None
        inv.invoice_class_token_final = kwargs.get('class_token')
        inv.title_final = kwargs.get('title_final', '')
        inv.subtotal_final = kwargs.get('subtotal_final', 10)
        inv.refactored_token = kwargs.get('refactored_token')
        inv.billing_id = kwargs.get('billing_id')
        inv.billing = Billing(kwargs['billing_id'], kwargs['billing_name']) if kwargs.get('billing_id') else None
        return inv

    def test_abono_or(self):
        meta = _invoice_column_meta(self._invoice(class_token='OR', invoice_class_id=2, subtotal_final=-5))
        self.assertEqual(meta['id'], 'abonament')

    def test_refactura(self):
        meta = _invoice_column_meta(self._invoice(
            class_token='OO', invoice_class_id=1, billing_id=5, billing_name='P',
            refactored_token='0123',
        ))
        self.assertEqual(meta['id'], 'refacturacio')

    def test_personalitzada(self):
        meta = _invoice_column_meta(self._invoice(class_token='OO', invoice_class_id=1, billing_id=None))
        self.assertEqual(meta['id'], 'personalitzada')

    def test_billing(self):
        meta = _invoice_column_meta(self._invoice(
            class_token='OO', invoice_class_id=1, billing_id=94, billing_name='Fact. RUTA 30',
        ))
        self.assertEqual(meta['id'], 94)
        self.assertEqual(meta['name'], 'Fact. RUTA 30')


class PadronColumnLabelTests(SimpleTestCase):
    def test_uses_billing_name(self):
        label = _padron_column_label({
            'name': 'Fact. RUTA 30 GOLF - EL PUNTO - 72026',
            'serie_finals': {'FC/202606/000200', 'FC/202606/000100'},
        })
        self.assertEqual(label, 'Fact. RUTA 30 GOLF - EL PUNTO - 72026')

    def test_fallback_without_name(self):
        self.assertEqual(_padron_column_label({}), 'Sense padró')


class WorkbookCanonSplitTests(SimpleTestCase):
    def test_execution_sheet_nests_canon_types_inside_zone(self):
        from collections import defaultdict

        from statistics.utils.report_billing_by_zone_service import (
            _empty_zone,
            build_workbook,
        )

        padrones = {
            1: {
                'id': 1,
                'name': 'Fact. RUTA 30 GOLF - EL PUNTO - 72026',
                'created_at': None,
                'sort': (-1, 0, 1),
                'serie_finals': {
                    'FC/202606/000100',
                    'FC/202606/000200',
                    'PF/171169',
                },
            },
        }
        zones = {1: {'id': 1, 'name': 'Zona 1', 'position': 1}}
        data = defaultdict(_empty_zone)
        data[(1, 1)]['invoice_ids'].add(10)
        data[(1, 1)]['quota']['base'] = 12.0
        data[(1, 1)]['quota']['invoice_ids'].add(10)
        data[(1, 1)]['canon']['CANON-DOM']['invoice_ids'].add(10)
        data[(1, 1)]['canon']['CANON-DOM']['trams'][1]['m3'] = 5.0
        data[(1, 1)]['canon']['CANON-DOM']['trams'][1]['base'] = 8.0

        wb = build_workbook(padrones, zones, data, {}, [], None, None)
        labels = [cell.value for cell in wb.active['A'] if cell.value]
        self.assertTrue(any('CANON-DOM' in str(v) for v in labels))
        self.assertTrue(any('CANON-MUN' in str(v) for v in labels))
        self.assertTrue(any('CANON-HOTELS' in str(v) for v in labels))
        self.assertTrue(any('CANON-IND' in str(v) for v in labels))
        self.assertTrue(any('CANON-DOM - TRAM 1' in str(v) for v in labels))
        self.assertTrue(any("CONSUM D'AIGUA - TRAM 1" in str(v) for v in labels))
        self.assertTrue(any('TOTAL CÀNON ZONA' in str(v) for v in labels))
        self.assertFalse(any(str(v).startswith('TOTAL ZONA:') for v in labels))
        self.assertFalse(any('Tarifa aigua' in str(v) for v in labels))
        self.assertEqual(sum(1 for v in labels if v == 'Quota servei'), 1)
        self.assertEqual(wb.sheetnames, [
            'Execució padrons', 'Factures', 'Comptadors actuals', 'Altres conceptes',
        ])
        self.assertEqual(wb.active['B1'].value, 'Fact. RUTA 30 GOLF - EL PUNTO - 72026')
        factures_headers = [cell.value for cell in wb.worksheets[1][1]]
        self.assertIn('Sèrie final', factures_headers)
        self.assertIn('Origen', factures_headers)
        self.assertNotIn('Tarifa aigua', factures_headers)

    def test_factures_sheet_lists_participating_invoices(self):
        from collections import defaultdict

        from statistics.utils.report_billing_by_zone_service import (
            _empty_zone,
            build_workbook,
        )

        padrones = {
            1: {
                'id': 1,
                'name': 'Fact. RUTA 30',
                'created_at': None,
                'sort': (-1, 0, 1),
                'serie_finals': set(),
            },
        }
        zones = {1: {'id': 1, 'name': 'Zona 1', 'position': 1}}
        data = defaultdict(_empty_zone)
        data[(1, 1)]['invoice_ids'].add(10)
        invoice_rows = [{
            'id': 10,
            'serie_final': 'FC/202606/000100',
            'origen': 'Fact. RUTA 30',
            'origen_kind': 'billing',
            'billing_id': 1,
            'billing_name': 'Fact. RUTA 30',
            'zone_id': 1,
            'zone_name': 'Zona 1',
            'issue_date': '2026-06-15',
            'contract_token': 'C1',
            'customer': 'Client Test',
            'invoice_class': 'Original',
            'consumption': 12.5,
            'subtotal': 40.0,
            'total': 48.4,
        }]
        wb = build_workbook(
            padrones, zones, data, {}, [], None, None, invoice_rows=invoice_rows,
        )
        sheet = wb['Factures']
        self.assertEqual(sheet['A2'].value, 'FC/202606/000100')
        self.assertEqual(sheet['B2'].value, 'Fact. RUTA 30')
        self.assertEqual(sheet['D2'].value, 'Zona 1')
        headers = [cell.value for cell in sheet[1]]
        self.assertIn('Zona', headers)
        self.assertNotIn('Zona id', headers)


class InformesFilterPayloadTests(SimpleTestCase):
    def test_period_from_date_range(self):
        from statistics.utils.report_billing_by_zone_service import _period_from_payload

        start, end = _period_from_payload({
            'date_range': ['2026-01-01T00:00:00.000Z', '2026-06-30T23:59:59.999Z'],
            'exploitation_id': 1,
            'billing_ids': [12, 13],
        })
        self.assertEqual(start.date().isoformat(), '2026-01-01')
        self.assertEqual(end.date().isoformat(), '2026-06-30')

    def test_period_from_start_end_dates(self):
        from statistics.utils.report_billing_by_zone_service import _period_from_payload

        start, end = _period_from_payload({
            'start_date': '2026-01-01',
            'end_date': '2026-03-31',
        })
        self.assertEqual(start.date().isoformat(), '2026-01-01')
        self.assertEqual(end.date().isoformat(), '2026-03-31')


class IncasolNumResolutionTests(TestCase):
    """`resolve_incasol_num` ha de prioritzar el número de l'explotació i caure al
    ConfigProject global quan l'explotació no en té, perquè les instal·lacions que
    encara no han omplert el camp no canviïn de comportament."""

    def setUp(self):
        self.exploitation = Exploitation.objects.create(name='Explotació A', token='A')

    def test_global_config_when_no_exploitation(self):
        ConfigProject.objects.create(token='incasol_num', name='Núm concert INCASOL', value='0000')
        self.assertEqual(resolve_incasol_num(None), '0000')

    def test_exploitation_value_wins(self):
        ConfigProject.objects.create(token='incasol_num', name='Núm concert INCASOL', value='0000')
        self.exploitation.incasol_num = '1234'
        self.exploitation.save()
        self.assertEqual(resolve_incasol_num(self.exploitation.id), '1234')

    def test_empty_exploitation_value_falls_back_to_global(self):
        ConfigProject.objects.create(token='incasol_num', name='Núm concert INCASOL', value='0000')
        self.exploitation.incasol_num = ''
        self.exploitation.save()
        self.assertEqual(resolve_incasol_num(self.exploitation.id), '0000')

    def test_unknown_exploitation_falls_back_to_global(self):
        ConfigProject.objects.create(token='incasol_num', name='Núm concert INCASOL', value='0000')
        self.assertEqual(resolve_incasol_num(999999), '0000')

    def test_default_when_nothing_configured(self):
        self.assertEqual(resolve_incasol_num(self.exploitation.id), '')

    def test_serializer_reads_and_writes_the_field(self):
        serializer = ExploitationSerializer(
            instance=self.exploitation,
            data={'incasol_num': '4321'},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.exploitation.refresh_from_db()
        self.assertEqual(self.exploitation.incasol_num, '4321')
        self.assertEqual(
            ExploitationSerializer(self.exploitation).data['incasol_num'], '4321'
        )

    def test_serializer_can_clear_the_field(self):
        self.exploitation.incasol_num = '4321'
        self.exploitation.save()
        serializer = ExploitationSerializer(
            instance=self.exploitation,
            data={'incasol_num': ''},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.exploitation.refresh_from_db()
        self.assertEqual(self.exploitation.incasol_num, '')
