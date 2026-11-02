import shutil
import tempfile
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from billing.models import Reading, ReadingAlert, ReadingDocument
from billing.tasks import _process_reading_document_file
from billing.utils.reading_document_import_service import build_reading_document_preview
from billing.utils.reading_service import (
    resolve_reading_document_previous_reading,
    resolve_reading_document_target_contract,
)
from contract.models import Contract, ContractStatus
from coredata.models import ConfigProject
from service.models import (
    Company, Meter, MeterStatus, Property, Route, RoutePosition, SupplyPoint, SupplyPointStatus,
)

MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class TestReadingDocumentContractResolution(TestCase):
    """
    Importing a tele-readings file (ReadingDocument) must attach each row to
    the contract that was in force at the reading date (registration_date /
    termination_date window) -- not to the newest active contract -- and must
    chain the reading to the previous reading that really precedes it, even
    when that reading belongs to the contract that preceded the current one.
    """

    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('contract_active_token', 'ACTIVE'),
            ('contract_terminated_status', 'TERMINATED'),
            ('invoice_type_invoice_token', 'F'),
            ('invoice_status_cancelled_token', 'CANCELLED'),
            ('invoice_status_pending_token', 'PENDING'),
            ('reading_alert_unusual_consumption', 'unusual_consumption'),
            ('reading_alert_negative', 'negative'),
        ):
            ConfigProject.objects.get_or_create(token=token, defaults={'value': value})
        cls.contract_status, _ = ContractStatus.objects.get_or_create(token='ACTIVE', defaults={'name': 'Alta'})
        cls.terminated_status, _ = ContractStatus.objects.get_or_create(token='TERMINATED', defaults={'name': 'Baixa'})
        cls.sp_status, _ = SupplyPointStatus.objects.get_or_create(token='SP_ACTIVE', defaults={'name': 'Actiu'})
        cls.meter_status, _ = MeterStatus.objects.get_or_create(token='1', defaults={'name': 'Actiu'})
        cls.company = Company.objects.create(name='Company reading doc resolution')
        for token in ('unusual_consumption', 'negative'):
            ReadingAlert.objects.get_or_create(token=token, defaults={'name': token.replace('_', ' ').title()})

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.route = Route.objects.create()
        self.position = RoutePosition.objects.create(route=self.route)
        self.prop = Property.objects.create(route_position=self.position)
        self.meter = Meter.objects.create(code='TEL-313', status=self.meter_status)
        self.sp = SupplyPoint.objects.create(
            token='TEL-SP-313', meter=self.meter, status=self.sp_status, property=self.prop,
        )
        self.old_contract = Contract.objects.create(
            company=self.company, token='C-OLD-313', status=self.terminated_status,
            is_active=True, supply_point_default=self.sp,
            registration_date=date(2024, 6, 1), termination_date=date(2025, 6, 30),
        )
        self.old_contract.supply_points.add(self.sp)
        self.new_contract = Contract.objects.create(
            company=self.company, token='C-NEW-313', status=self.contract_status,
            is_active=True, supply_point_default=self.sp,
            registration_date=date(2025, 7, 1),
        )
        self.new_contract.supply_points.add(self.sp)

    def _document(self, *rows):
        """
        rows: (meter_code, reading_value, reading_date) triplets. The default
        template maps the natural column names of the tele-readings file.
        """
        lines = ["meter,reading_value,reading,reading_date"]
        for meter_code, value, date_str in rows:
            lines.append(f"{meter_code},{value},{value},{date_str}")
        return ReadingDocument.objects.create(
            token='DOC-313',
            file=SimpleUploadedFile(
                'telelectures.csv', ("\n".join(lines) + "\n").encode('utf-8'), 'text/csv',
            ),
        )

    def _first_row_last_reading(self, reading):
        return Reading.objects.get(id=reading.previous_reading_id)

    def test_row_in_old_contract_period_gets_terminated_but_valid_contract(self):
        Reading.objects.create(
            meter=self.meter, contract=self.old_contract, supply_point=self.sp,
            reading_date=date(2025, 1, 2), reading_value=100, calculated_value=0,
        )
        document = self._document(('TEL-313', '150', '2025-03-15'))

        stats = _process_reading_document_file(document, document.file, document.id)

        reading = Reading.objects.get(document=document)
        self.assertEqual(stats["created"], 1)
        self.assertEqual(reading.contract, self.old_contract)
        self.assertEqual(reading.supply_point, self.sp)
        self.assertEqual(reading.previous_reading.reading_value, 100)
        self.assertEqual(reading.calculated_value, 50)
        self.assertEqual(reading.consumption_days, 72)
        self.assertEqual(document.not_found_readings.count(), 0)

    def test_row_in_new_contract_period_chains_previous_from_other_contract(self):
        Reading.objects.create(
            meter=self.meter, contract=self.old_contract, supply_point=self.sp,
            reading_date=date(2025, 5, 2), reading_value=200, calculated_value=0,
        )
        document = self._document(('TEL-313', '450', '2025-09-15'))

        stats = _process_reading_document_file(document, document.file, document.id)

        reading = Reading.objects.get(document=document)
        self.assertEqual(stats["created"], 1)
        self.assertEqual(reading.contract, self.new_contract)
        self.assertEqual(reading.previous_reading.contract, self.old_contract)
        self.assertEqual(reading.previous_reading.reading_value, 200)
        self.assertEqual(reading.calculated_value, 250)
        self.assertEqual(stats["previous_from_other_contract"], 1)

    def test_row_without_valid_contract_is_skipped(self):
        document = self._document(('TEL-313', '150', '2024-05-25'))

        stats = _process_reading_document_file(document, document.file, document.id)

        self.assertEqual(stats["no_contracts"], 1)
        self.assertFalse(Reading.objects.filter(document=document).exists())

    def test_update_branch_recomputes_previous_and_consumption(self):
        contract = Contract.objects.create(
            company=self.company, token='C-SINGLE-313', status=self.contract_status,
            is_active=True, supply_point_default=self.sp,
            registration_date=date(2024, 1, 1),
        )
        contract.supply_points.add(self.sp)
        old_previous = Reading.objects.create(
            meter=self.meter, contract=contract, supply_point=self.sp,
            reading_date=date(2026, 1, 2), reading_value=100, calculated_value=0,
        )
        overwritten = Reading.objects.create(
            meter=self.meter, contract=contract, supply_point=self.sp,
            reading_date=date(2026, 7, 2), reading_value=200,
            calculated_value=100, previous_reading=old_previous, consumption_days=181,
        )
        document = self._document(('TEL-313', '210', '2026-07-20'))

        stats = _process_reading_document_file(document, document.file, document.id)

        self.assertEqual(stats["updated"], 1)
        overwritten.refresh_from_db()
        self.assertEqual(overwritten.reading_value, 210)
        self.assertEqual(overwritten.reading_date, date(2026, 7, 20))
        self.assertEqual(overwritten.document, document)
        self.assertEqual(overwritten.previous_reading, old_previous)
        self.assertEqual(overwritten.calculated_value, 110)
        self.assertEqual(overwritten.consumption_days, 199)

    def test_update_branch_chains_previous_of_other_contract(self):
        contract = Contract.objects.create(
            company=self.company, token='C-SINGLE-313', status=self.contract_status,
            is_active=True, supply_point_default=self.sp,
            registration_date=date(2024, 1, 1),
        )
        contract.supply_points.add(self.sp)
        # The only preceding reading belongs to the contract before this one
        # (change of ownership): the overwritten row must chain to it.
        other_contract = Contract.objects.create(
            company=self.company, token='C-OTHER-313', status=self.terminated_status,
            is_active=True, registration_date=date(2025, 1, 1), termination_date=date(2026, 2, 1),
        )
        other_contract.supply_points.add(self.sp)
        stray = Reading.objects.create(
            meter=self.meter, contract=other_contract, supply_point=self.sp,
            reading_date=date(2026, 1, 10), reading_value=120, calculated_value=0,
        )
        overwritten = Reading.objects.create(
            meter=self.meter, contract=contract, supply_point=self.sp,
            reading_date=date(2026, 2, 2), reading_value=200,
            calculated_value=100, consumption_days=181,
        )
        document = self._document(('TEL-313', '210', '2026-02-20'))

        stats = _process_reading_document_file(document, document.file, document.id)

        self.assertEqual(stats["updated"], 1)
        overwritten.refresh_from_db()
        self.assertEqual(overwritten.previous_reading, stray)
        self.assertEqual(overwritten.calculated_value, 90)
        self.assertEqual(stats["previous_from_other_contract"], 1)

    def test_preview_matches_process_for_contract_and_previous(self):
        Reading.objects.create(
            meter=self.meter, contract=self.old_contract, supply_point=self.sp,
            reading_date=date(2025, 1, 2), reading_value=100, calculated_value=0,
        )
        document = self._document(('TEL-313', '150', '2025-03-15'))

        preview = build_reading_document_preview(document)

        row = preview["rows"][0]
        self.assertEqual(row["action"], "would_create")
        self.assertEqual(row["contract_token"], 'C-OLD-313')
        self.assertEqual(row["previous_reading_value"], 100)
        self.assertEqual(row["previous_reading_contract_token"], 'C-OLD-313')
        self.assertFalse(row["previous_from_other_contract"])

    def test_preview_flags_previous_reading_of_other_contract(self):
        Reading.objects.create(
            meter=self.meter, contract=self.old_contract, supply_point=self.sp,
            reading_date=date(2025, 5, 2), reading_value=200, calculated_value=0,
        )
        document = self._document(('TEL-313', '450', '2025-09-15'))

        preview = build_reading_document_preview(document)

        row = preview["rows"][0]
        self.assertEqual(row["action"], "would_create")
        self.assertEqual(row["contract_token"], 'C-NEW-313')
        self.assertEqual(row["previous_reading_value"], 200)
        self.assertEqual(row["previous_reading_contract_token"], 'C-OLD-313')
        self.assertTrue(row["previous_from_other_contract"])
        self.assertEqual(preview["stats"]["previous_from_other_contract"], 1)

    def test_resolver_prefers_active_status_within_overlapping_windows(self):
        # Overlapping change of ownership: both cover the date, the active
        # one (the contract currently in force) wins.
        Contract.objects.filter(id=self.new_contract.id).update(
            registration_date=date(2025, 6, 1)
        )
        resolved = resolve_reading_document_target_contract(
            self.sp, date(2025, 6, 15)
        )
        self.assertEqual(resolved, self.new_contract)

    def test_resolver_uses_m2m_contract_without_supply_point_default(self):
        m2m_only = Contract.objects.create(
            company=self.company, token='C-M2M-313', status=self.contract_status,
            is_active=True,
            registration_date=date(2023, 1, 1), termination_date=date(2024, 3, 31),
        )
        m2m_only.supply_points.add(self.sp)
        # A date only covered by the M2M contract (no supply_point_default).
        resolved = resolve_reading_document_target_contract(self.sp, date(2023, 5, 15))
        self.assertEqual(resolved, m2m_only)

    def test_previous_resolver_excludes_given_reading(self):
        first = Reading.objects.create(
            meter=self.meter, contract=self.old_contract, supply_point=self.sp,
            reading_date=date(2025, 1, 2), reading_value=100, calculated_value=0,
        )
        second = Reading.objects.create(
            meter=self.meter, contract=self.old_contract, supply_point=self.sp,
            reading_date=date(2025, 3, 2), reading_value=150,
            calculated_value=50, previous_reading=first,
        )

        previous, tier = resolve_reading_document_previous_reading(
            supply_point=self.sp, meter=self.meter, contract=self.old_contract,
            reading_date=date(2025, 4, 10), exclude_reading=second,
        )
        self.assertEqual(previous, first)
        self.assertEqual(tier, 1)
