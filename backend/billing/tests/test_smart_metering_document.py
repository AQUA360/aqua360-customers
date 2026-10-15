import shutil
import tempfile
from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

import openpyxl
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from billing.models import Reading, ReadingBatch, ReadingDocument
from billing.utils.smart_metering_service import (
    build_smart_metering_preview,
    import_smart_metering_readings,
    smart_metering_document_is_replaceable,
)
from billing.views.reading_document_view import ReadingDocumentViewSet
from contract.models import Contract, ContractStatus
from coredata.models import ConfigProject
from service.models import Company, Meter, MeterStatus, SupplyPoint, SupplyPointStatus

MEDIA_ROOT = tempfile.mkdtemp()
READING_DATE = date(2026, 10, 1)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class TestSmartMeteringDocument(TestCase):
    """
    The Smart Metering load lives in "Introduir lectures": it creates a reading
    document (with an Excel file) that is not tied to any reading batch.
    """

    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('contract_active_token', 'ACTIVE'),
            ('contract_terminated_status', 'TERMINATED'),
            ('contract_termination_completed_token', 'COMPLETED'),
            ('token_meter_status_no_meter', 'NO_METER'),
        ):
            ConfigProject.objects.get_or_create(token=token, defaults={'value': value})
        cls.contract_status, _ = ContractStatus.objects.get_or_create(token='ACTIVE', defaults={'name': 'Alta'})
        cls.sp_status, _ = SupplyPointStatus.objects.get_or_create(token='SP_ACTIVE', defaults={'name': 'Actiu'})
        cls.meter_status, _ = MeterStatus.objects.get_or_create(token='1', defaults={'name': 'Actiu'})
        cls.company = Company.objects.create(name='Company smart metering')
        cls.user = get_user_model().objects.create_superuser(username='smart-metering', password='x', email='')

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.meter = Meter.objects.create(
            code='SM-0001', status=self.meter_status,
            has_remote_reading=True, remote_reading_type='SMART_METERING',
        )
        self.sp = SupplyPoint.objects.create(token='SM-SP-1', meter=self.meter, status=self.sp_status)
        self.contract = Contract.objects.create(
            company=self.company, token='SM-C-1', status=self.contract_status,
            is_active=True, supply_point_default=self.sp,
        )
        self.contract.supply_points.add(self.sp)
        self.previous = Reading.objects.create(
            meter=self.meter, contract=self.contract, supply_point=self.sp,
            reading_date=date(2026, 7, 1), reading_value=100, calculated_value=0,
        )
        # A manual meter must not be part of the Smart Metering load.
        manual_meter = Meter.objects.create(code='MAN-0001', status=self.meter_status)
        manual_sp = SupplyPoint.objects.create(token='MAN-SP-1', meter=manual_meter, status=self.sp_status)
        manual_contract = Contract.objects.create(
            company=self.company, token='MAN-C-1', status=self.contract_status,
            is_active=True, supply_point_default=manual_sp,
        )
        manual_contract.supply_points.add(manual_sp)

    def _api_payload(self, reading_value=130):
        return [{'meter': 'SM-0001', 'reading': reading_value, 'timestamp': READING_DATE.isoformat()}]

    def _new_document(self):
        return ReadingDocument.objects.create(
            token='SM-DOC',
            source=ReadingDocument.SOURCE_SMART_METERING,
            reading_date=READING_DATE,
            status=ReadingDocument.STATUS_PROCESSING,
        )

    def _import(self, document, reading_value=130):
        with patch(
            'billing.utils.smart_metering_service.SmartMeteringClient.fetch_readings',
            return_value=self._api_payload(reading_value),
        ):
            return import_smart_metering_readings(document)

    def test_preview_covers_smart_metering_meters_without_batch(self):
        with patch(
            'billing.utils.smart_metering_service.SmartMeteringClient.fetch_readings',
            return_value=self._api_payload(),
        ):
            preview = build_smart_metering_preview(READING_DATE.isoformat())

        self.assertEqual([row['meter_code'] for row in preview['readings']], ['SM-0001'])
        self.assertTrue(preview['readings'][0]['matched'])
        self.assertEqual(preview['readings'][0]['last_previous_reading_value'], 100.0)

    def test_import_creates_document_readings_and_excel(self):
        document = self._new_document()

        result = self._import(document)

        document.refresh_from_db()
        self.assertEqual(result['saved_readings'], 1)
        self.assertEqual(document.status, ReadingDocument.STATUS_PROCESSED)
        reading = document.readings.get(is_control=False)
        self.assertIsNone(reading.batch_id)
        self.assertEqual(reading.reading_value, Decimal('130'))
        self.assertEqual(reading.previous_reading_id, self.previous.id)
        self.assertEqual(reading.calculated_value, Decimal('30'))

        self.assertIn('smart_metering_20261001', document.file.name)
        self.assertTrue(document.file.name.endswith('.xlsx'))
        with document.file.open('rb') as fh:
            wb = openpyxl.load_workbook(BytesIO(fh.read()))
        rows = list(wb['readings'].iter_rows(min_row=2, values_only=True))
        self.assertEqual(rows[0][0], 'SM-0001')
        self.assertEqual(rows[0][1], 130.0)

    def test_reload_same_document_does_not_duplicate_readings(self):
        document = self._new_document()
        self._import(document)

        self._import(document)

        self.assertEqual(document.readings.filter(is_control=False).count(), 1)
        self.assertEqual(
            Reading.objects.filter(meter=self.meter, reading_date=READING_DATE, is_control=False).count(), 1
        )

    def test_reading_used_by_a_batch_is_not_modified(self):
        batch = ReadingBatch.objects.create(name='Lot')
        batch_reading = Reading.objects.create(
            meter=self.meter, contract=self.contract, supply_point=self.sp, batch=batch,
            previous_reading=self.previous, reading_date=READING_DATE, reading_value=120, calculated_value=20,
        )
        document = self._new_document()

        result = self._import(document, reading_value=130)

        batch_reading.refresh_from_db()
        self.assertEqual(result['saved_readings'], 0)
        self.assertEqual(result['not_saved_readings'], 1)
        self.assertFalse(batch_reading.is_control)
        self.assertEqual(batch_reading.batch_id, batch.id)
        self.assertIsNone(batch_reading.document_id)
        self.assertFalse(document.readings.exists())

    def test_document_is_replaceable_until_used_by_a_batch(self):
        document = self._new_document()
        self._import(document)
        self.assertTrue(smart_metering_document_is_replaceable(document))

        document.batch = ReadingBatch.objects.create(name='Lot')
        document.save(update_fields=['batch'])

        self.assertFalse(smart_metering_document_is_replaceable(document))

    def _post_import(self, replace=False):
        view = ReadingDocumentViewSet.as_view({'post': 'smart_metering_import'})
        request = APIRequestFactory().post(
            '/billing/reading-document/smart-metering/import/',
            {'reading_date': READING_DATE.isoformat(), 'preview': None, 'replace': replace},
            format='json',
        )
        force_authenticate(request, user=self.user)
        with patch('billing.views.reading_document_view.import_smart_metering_document_task.delay') as delay:
            delay.return_value.id = 'task-id'
            return view(request)

    def test_import_endpoint_blocks_repeated_date_unless_replace(self):
        first = self._post_import()
        self.assertEqual(first.status_code, 202, first.data)
        document = ReadingDocument.objects.get(id=first.data['document_id'])
        document.status = ReadingDocument.STATUS_PROCESSED
        document.save(update_fields=['status'])

        repeated = self._post_import()
        self.assertEqual(repeated.status_code, 409)
        self.assertTrue(repeated.data['existing_document']['replaceable'])

        replaced = self._post_import(replace=True)
        self.assertEqual(replaced.status_code, 202, replaced.data)
        self.assertEqual(replaced.data['document_id'], document.id)
        self.assertEqual(
            ReadingDocument.objects.filter(source=ReadingDocument.SOURCE_SMART_METERING).count(), 1
        )

    def test_import_endpoint_blocks_replace_when_document_is_in_a_batch(self):
        first = self._post_import()
        document = ReadingDocument.objects.get(id=first.data['document_id'])
        document.status = ReadingDocument.STATUS_PROCESSED
        document.batch = ReadingBatch.objects.create(name='Lot')
        document.save(update_fields=['status', 'batch'])

        response = self._post_import(replace=True)

        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.data['existing_document']['replaceable'])
