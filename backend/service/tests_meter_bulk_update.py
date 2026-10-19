"""Tests per l'update massiva de Meter (preview + confirm)."""
import io
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from service.models import Meter, MeterCaliber, MeterStatus
from service.utils.meter_bulk_update_service import (
    MeterBulkUpdateError,
    apply_updates,
    build_preview,
    parse_meter_bulk_file,
)
from service.views.meter_view import MeterViewSet


def _csv_file(content, name='meters.csv'):
    buf = io.BytesIO(content.encode('utf-8-sig'))
    buf.name = name
    return buf


class TestMeterBulkUpdateService(TestCase):
    def setUp(self):
        self.status_actiu = MeterStatus.objects.create(token='actiu', name='Actiu')
        self.status_baixa = MeterStatus.objects.create(token='baixa', name='Baixa')
        self.caliber_15 = MeterCaliber.objects.create(token='15', name='15')
        self.caliber_20 = MeterCaliber.objects.create(token='20', name='20')
        self.meter_a = Meter.objects.create(
            code='M-001',
            code2='OLD',
            status=self.status_actiu,
            caliber=self.caliber_15,
            has_remote_reading=False,
            manufacturer='Acme',
        )
        self.meter_b = Meter.objects.create(
            code='M-002',
            code2='KEEP',
            status=self.status_actiu,
            has_remote_reading=False,
        )

    def test_preview_found_not_found_and_changes(self):
        csv_content = (
            "code;code2;status;HasRemoteReading\n"
            "M-001;NEW;baixa;true\n"
            "M-999;X;actiu;false\n"
            "M-002;KEEP;actiu;false\n"
        )
        result = build_preview(_csv_file(csv_content))

        self.assertEqual(result['stats']['total_rows'], 3)
        self.assertEqual(result['stats']['to_update'], 1)
        self.assertEqual(result['stats']['not_found'], 1)
        self.assertEqual(result['stats']['unchanged'], 1)
        self.assertEqual(result['not_found'], ['M-999'])

        update = result['updates'][0]
        self.assertEqual(update['code'], 'M-001')
        self.assertEqual(update['changes']['code2']['old'], 'OLD')
        self.assertEqual(update['changes']['code2']['new'], 'NEW')
        self.assertEqual(update['changes']['status']['new']['token'], 'baixa')
        self.assertTrue(update['changes']['has_remote_reading']['new'])

        # Preview no desa
        self.meter_a.refresh_from_db()
        self.assertEqual(self.meter_a.code2, 'OLD')
        self.assertEqual(self.meter_a.status_id, self.status_actiu.id)

    def test_confirm_applies_and_respects_empty_cells(self):
        csv_content = (
            "Code;code2;manufacturer;status\n"
            "M-001;UPDATED;;baixa\n"
        )
        result = apply_updates(_csv_file(csv_content))

        self.assertEqual(result['stats']['updated'], 1)
        self.meter_a.refresh_from_db()
        self.assertEqual(self.meter_a.code2, 'UPDATED')
        self.assertEqual(self.meter_a.manufacturer, 'Acme')  # cel·la buida = no tocar
        self.assertEqual(self.meter_a.status_id, self.status_baixa.id)

    def test_external_csv_preserves_original_apostrophes(self):
        for delimiter in (';', ','):
            with self.subTest(delimiter=delimiter):
                content = delimiter.join(['code', 'code2', 'model']) + '\n'
                content += delimiter.join(['M-001', "'=1+1", "''=1+1"]) + '\n'
                result = apply_updates(_csv_file(content))
                self.assertEqual(result['stats']['errors'], 0)
                self.meter_a.refresh_from_db()
                self.assertEqual(self.meter_a.code2, "'=1+1")
                self.assertEqual(self.meter_a.model, "''=1+1")

    def test_meter_export_identifies_reversible_encoding(self):
        from documentmanager.utils.csv_safety import CSV_ESCAPE_MARKER
        from service.tasks import export_meters_csv_task
        from service.utils.meter_bulk_update_service import _parse_csv_bytes

        self.meter_a.code2 = "'=1+1"
        self.meter_a.model = '=1+1'
        self.meter_a.save()
        with patch('documentmanager.utils.main_utils.upload_document') as upload:
            result = export_meters_csv_task()
        self.assertEqual(result['status'], 'success', result)
        content = upload.call_args.kwargs['file'].read()
        self.assertIn(CSV_ESCAPE_MARKER.encode(), content)
        rows = _parse_csv_bytes(content)
        row = next(row for row in rows[1:] if row[rows[0].index('code')] == 'M-001')
        self.assertEqual(row[rows[0].index('code2')], "'=1+1")
        self.assertEqual(row[rows[0].index('model')], '=1+1')

    def test_lookup_export_identifies_reversible_encoding(self):
        from documentmanager.utils.csv_safety import CSV_ESCAPE_MARKER
        from service.utils.meter_bulk_update_service import _parse_csv_bytes
        from service.utils.meter_lookup_service import build_meter_lookup_csv_bytes

        self.meter_a.manufacturer = "'=1+1"
        self.meter_a.save()
        content, found, not_found = build_meter_lookup_csv_bytes(['M-001'])
        self.assertEqual((found, not_found), (1, 0))
        self.assertIn(CSV_ESCAPE_MARKER.encode(), content)
        rows = _parse_csv_bytes(content)
        self.assertEqual(rows[1][rows[0].index('Manufacturer')], "'=1+1")

    def test_unknown_column_raises(self):
        csv_content = "code;foo_bar\nM-001;x\n"
        with self.assertRaises(MeterBulkUpdateError) as ctx:
            parse_meter_bulk_file(_csv_file(csv_content))
        self.assertIn('foo_bar', str(ctx.exception))

    def test_is_active_column_rejected(self):
        csv_content = "code;is_active\nM-001;false\n"
        with self.assertRaises(MeterBulkUpdateError) as ctx:
            parse_meter_bulk_file(_csv_file(csv_content))
        self.assertIn('is_active', str(ctx.exception))

    def test_caliber_by_token(self):
        csv_content = "code;caliber\nM-001;20\n"
        result = apply_updates(_csv_file(csv_content))
        self.assertEqual(result['stats']['updated'], 1)
        self.meter_a.refresh_from_db()
        self.assertEqual(self.meter_a.caliber_id, self.caliber_20.id)

    def test_invalid_status_is_error_row(self):
        csv_content = "code;status\nM-001;inexistent\n"
        result = build_preview(_csv_file(csv_content))
        self.assertEqual(result['stats']['errors'], 1)
        self.assertEqual(result['stats']['to_update'], 0)
        self.assertIn('MeterStatus', result['errors'][0]['message'])

    def test_confirm_partial_applies_valid_rows(self):
        csv_content = (
            "code;code2\n"
            "M-001;OK\n"
            "MISSING;NO\n"
        )
        result = apply_updates(_csv_file(csv_content))
        self.assertEqual(result['stats']['updated'], 1)
        self.assertEqual(result['not_found'], ['MISSING'])
        self.meter_a.refresh_from_db()
        self.assertEqual(self.meter_a.code2, 'OK')

    def test_duplicate_code_in_file_preview_matches_confirm(self):
        """Mateix code dues vegades: la 2a fila queda unchanged (ja aplicat en memòria)."""
        csv_content = (
            "code;caliber\n"
            "M-001;20\n"
            "M-002;20\n"
            "M-001;20\n"
        )
        preview = build_preview(_csv_file(csv_content))
        self.assertEqual(preview['stats']['to_update'], 2)
        self.assertEqual(preview['stats']['unchanged'], 1)
        self.assertEqual(preview['duplicate_codes_in_file'], ['M-001'])
        self.assertEqual(preview['unchanged'][0]['row'], 4)
        self.assertEqual(
            preview['unchanged'][0]['reason'],
            'already_updated_earlier_in_file',
        )

        # Preview no desa
        self.meter_a.refresh_from_db()
        self.assertEqual(self.meter_a.caliber_id, self.caliber_15.id)

        confirm = apply_updates(_csv_file(csv_content))
        self.assertEqual(confirm['stats']['updated'], 2)
        self.assertEqual(confirm['stats']['unchanged'], 1)
        self.assertEqual(confirm['duplicate_codes_in_file'], ['M-001'])
        self.meter_a.refresh_from_db()
        self.assertEqual(self.meter_a.caliber_id, self.caliber_20.id)


class TestMeterBulkUpdateEndpoints(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username='bulkuser', password='password')
        ct = ContentType.objects.get_for_model(Meter)
        perm = Permission.objects.get(content_type=ct, codename='change_meter')
        self.user.user_permissions.add(perm)

        self.status_actiu = MeterStatus.objects.create(token='actiu', name='Actiu')
        self.meter = Meter.objects.create(code='E-100', code2='BEFORE', status=self.status_actiu)

    def test_preview_endpoint(self):
        view = MeterViewSet.as_view({'post': 'bulk_update_preview'})
        csv_content = "code;code2\nE-100;AFTER\nUNKNOWN;X\n"
        request = self.factory.post(
            '/service/meter/bulk-update/preview/',
            {'file': _csv_file(csv_content)},
            format='multipart',
        )
        force_authenticate(request, user=self.user)
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['stats']['to_update'], 1)
        self.assertEqual(response.data['not_found'], ['UNKNOWN'])
        self.meter.refresh_from_db()
        self.assertEqual(self.meter.code2, 'BEFORE')

    def test_confirm_endpoint(self):
        view = MeterViewSet.as_view({'post': 'bulk_update_confirm'})
        csv_content = "code;code2\nE-100;AFTER\n"
        request = self.factory.post(
            '/service/meter/bulk-update/confirm/',
            {'file': _csv_file(csv_content)},
            format='multipart',
        )
        force_authenticate(request, user=self.user)
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['stats']['updated'], 1)
        self.meter.refresh_from_db()
        self.assertEqual(self.meter.code2, 'AFTER')

    def test_missing_file_returns_400(self):
        view = MeterViewSet.as_view({'post': 'bulk_update_preview'})
        request = self.factory.post('/service/meter/bulk-update/preview/', {}, format='multipart')
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertEqual(response.status_code, 400)

    def test_without_permission_returns_403(self):
        other = User.objects.create_user(username='noperm', password='password')
        view = MeterViewSet.as_view({'post': 'bulk_update_preview'})
        csv_content = "code;code2\nE-100;X\n"
        request = self.factory.post(
            '/service/meter/bulk-update/preview/',
            {'file': _csv_file(csv_content)},
            format='multipart',
        )
        force_authenticate(request, user=other)
        response = view(request)
        self.assertEqual(response.status_code, 403)
