"""Regression checks for bulk replacement validation and confirmation."""
import io
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory, force_authenticate

from service.utils import meter_bulk_change_service as bulk
from service.views.meter_view import MeterViewSet


def csv_file(text):
    result = io.BytesIO(text.encode())
    result.name = 'meters.csv'
    return result


class BulkChangeTests(SimpleTestCase):
    def analysis(self, create=None):
        return {
            'rows': [{}], 'changes': [{'new_meter': {'will_create': create is not None}}],
            'ready': [{'row': 2, 'code': 'OLD', 'new_code': 'NEW',
                       'supply_point_id': 1, 'old_meter_id': 2, 'new_meter_id': 3,
                       'create_meter': create, 'change_date': '2026-01-01',
                       'final_reading': 10, 'initial_reading': 0}],
            'not_found': [], 'errors': [], 'duplicate_codes': [], 'active_status': None,
        }

    def test_inactive_code_blocks_creation(self):
        all_meters = Mock()
        all_meters.values_list.return_value = ['OLD', 'NEW']
        with patch.object(bulk.Meter.objects, 'filter', side_effect=[
            all_meters, [SimpleNamespace(code='OLD', id=2)],
        ]) as meters, patch.object(bulk.SupplyPoint.objects, 'filter') as points:
            points.return_value.select_related.return_value = []
            result = bulk.build_preview(csv_file(
                'code,new_code,final_reading,initial_reading,create_new_meter\nOLD,NEW,10,0,si\n'))
        self.assertEqual(result['stats']['to_create'], 0)
        self.assertIn('ja existeix', result['errors'][0]['message'])
        self.assertEqual(meters.call_args_list[1].kwargs['is_active'], True)
        self.assertNotIn('is_active', meters.call_args_list[0].kwargs)

    def run_confirmation(self, analysis, current_meter=2, error=None):
        with patch.object(bulk, '_analyse', return_value=analysis), \
                patch.object(bulk.transaction, 'atomic'), \
                patch.object(bulk.SupplyPoint.objects, 'select_for_update') as lock, \
                patch.object(bulk.Meter.objects, 'create') as create, \
                patch.object(bulk.MeterChangeService, 'apply', side_effect=error) as apply:
            lock.return_value.get.return_value.meter_id = current_meter
            result = bulk.apply_changes(None, Mock())
            lock.assert_called_once_with()
            return result, create, apply

    def test_changed_assignment_skips_creation_and_apply(self):
        result, create, apply = self.run_confirmation(self.analysis({}), current_meter=99)
        create.assert_not_called()
        apply.assert_not_called()
        self.assertEqual(result['stats']['failed'], 1)
        self.assertEqual(result['stats']['changed'], 0)

    def test_unexpected_row_exception_is_private(self):
        with self.assertLogs(bulk.logger, level='ERROR'):
            result, _, _ = self.run_confirmation(self.analysis(), error=RuntimeError('private detail'))
        self.assertNotIn('private detail', str(result))
        self.assertEqual(result['errors'][0]['row'], 2)
        self.assertEqual(result['errors'][0]['code'], 'OLD')

    def test_change_permission_allows_reuse(self):
        result, _, apply = self.run_confirmation(self.analysis())
        apply.assert_called_once()
        self.assertEqual(result['stats']['changed'], 1)

    def test_creation_requires_add_permission_before_mutations(self):
        user = Mock()
        user.has_perm.return_value = False
        with patch.object(bulk, '_analyse', return_value=self.analysis({})), \
                patch.object(bulk.transaction, 'atomic') as atomic:
            with self.assertRaises(PermissionDenied):
                bulk.apply_changes(None, user)
        atomic.assert_not_called()
        user.has_perm.assert_called_once_with('service.add_meter')

    def preview_request(self, file):
        request = APIRequestFactory().post('/', {'file': file}, format='multipart')
        user = Mock(is_authenticated=True)
        user.has_perm.return_value = True
        force_authenticate(request, user=user)
        return MeterViewSet.as_view({'post': 'bulk_change_preview'})(request)

    def test_missing_column_diagnostic_is_public(self):
        response = self.preview_request(csv_file('code,new_code,final_reading\nOLD,NEW,10\n'))
        self.assertEqual(response.status_code, 400)
        self.assertIn('initial_reading', response.data['error'])

    def test_parser_details_are_private(self):
        with patch.object(bulk.pd, 'read_csv', side_effect=RuntimeError('private parser detail')), \
                self.assertLogs('service.views.meter_view', level='ERROR'):
            response = self.preview_request(csv_file('invalid'))
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('private parser detail', str(response.data))

    def test_confirm_api_rejects_creation_without_add_permission(self):
        request = APIRequestFactory().post('/', {'file': csv_file('unused')}, format='multipart')
        user = Mock(is_authenticated=True)
        user.has_perm.side_effect = lambda perm: perm == 'service.change_meter'
        force_authenticate(request, user=user)
        with patch.object(bulk, '_analyse', return_value=self.analysis({})), \
                patch.object(bulk.Meter.objects, 'create') as create:
            response = MeterViewSet.as_view({'post': 'bulk_change_confirm'})(request)
        self.assertEqual(response.status_code, 403)
        create.assert_not_called()
