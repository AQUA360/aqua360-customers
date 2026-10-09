import json
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from integrations.outbound.giswater.mappers import (
    build_connection_updates_by_token,
    extract_connec_fields,
    filter_esco_connecs,
    map_connec_to_connection_values,
    map_mincut_to_supply_cut_dates,
    to_aware_datetime,
    to_decimal,
)
from integrations.outbound.giswater.sync import sync_connections_from_giswater
from service.models import Connection


SAMPLE_RESPONSE = {
    "body": {
        "data": {
            "fields": [
                {
                    "connec_id": 12547,
                    "connec_type": "ESCO",
                    "customer_code": "3410103",
                    "lat": 41.48061398054251,
                    "long": 2.32357789570044,
                },
                {
                    "connec_id": 99999,
                    "connec_type": "OTHER",
                    "customer_code": "0000000",
                    "lat": 1.0,
                    "long": 2.0,
                },
                {
                    "connec_id": 12546,
                    "connec_type": "ESCO",
                    "customer_code": "",
                    "lat": 41.47,
                    "long": 2.29,
                },
            ]
        }
    }
}


class GiswaterMappersTest(TestCase):
    def test_extract_connec_fields(self):
        fields = extract_connec_fields(SAMPLE_RESPONSE)
        self.assertEqual(len(fields), 3)

    def test_filter_esco_connecs(self):
        fields = extract_connec_fields(SAMPLE_RESPONSE)
        esco = filter_esco_connecs(fields)
        self.assertEqual(len(esco), 2)

    def test_map_connec_to_connection_values(self):
        mapped = map_connec_to_connection_values(SAMPLE_RESPONSE["body"]["data"]["fields"][0])
        self.assertEqual(
            mapped,
            {
                "customer_code": "3410103",
                "code_gis": "12547",
                "latitude": Decimal("41.480614"),
                "longitude": Decimal("2.323578"),
            },
        )

    def test_map_connec_without_customer_code_returns_none(self):
        fields = extract_connec_fields(SAMPLE_RESPONSE)
        mapped = map_connec_to_connection_values(fields[2])
        self.assertIsNone(mapped)

    def test_build_connection_updates_by_token(self):
        fields = extract_connec_fields(SAMPLE_RESPONSE)
        updates, skipped = build_connection_updates_by_token(fields)
        self.assertEqual(skipped, 1)
        self.assertEqual(updates["3410103"]["code_gis"], "12547")

    def test_to_decimal_invalid(self):
        self.assertIsNone(to_decimal("invalid"))


class SyncGiswaterConnectionsTest(TestCase):
    def test_sync_updates_matching_connection(self):
        Connection.objects.create(token="3410103", code_gis=None)

        with patch(
            "integrations.outbound.giswater.sync.fetch_connecs",
            return_value=SAMPLE_RESPONSE,
        ):
            stats = sync_connections_from_giswater()

        connection = Connection.objects.get(token="3410103")
        self.assertEqual(stats["updated"], 1)
        self.assertEqual(connection.code_gis, "12547")
        self.assertEqual(connection.latitude, Decimal("41.480614"))
        self.assertEqual(connection.longitude, Decimal("2.323578"))

    def test_sync_counts_not_found(self):
        with patch(
            "integrations.outbound.giswater.sync.fetch_connecs",
            return_value=SAMPLE_RESPONSE,
        ):
            stats = sync_connections_from_giswater()

        self.assertEqual(stats["not_found"], 1)
        self.assertEqual(len(stats["not_found_tokens"]), 1)
        self.assertEqual(stats["not_found_tokens"][0]["customer_code"], "3373640")

    def test_sync_with_saved_fixture_structure(self):
        fixture_path = Path(__file__).resolve().parent / "fixtures" / "connecs_sample.json"
        if not fixture_path.exists():
            self.skipTest("Fixture JSON no disponible")

        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        fields = extract_connec_fields(payload)
        updates, _ = build_connection_updates_by_token(fields)

        self.assertGreater(len(fields), 0)
        self.assertGreater(len(updates), 0)
        self.assertTrue(all(values["code_gis"] for values in updates.values()))


class ToAwareDatetimeTest(TestCase):
    def test_empty_returns_none(self):
        self.assertIsNone(to_aware_datetime(None))
        self.assertIsNone(to_aware_datetime(""))
        self.assertIsNone(to_aware_datetime("   "))
        self.assertIsNone(to_aware_datetime("no-es-una-data"))

    def test_naive_string_becomes_aware(self):
        dt = to_aware_datetime("2026-09-07 08:00:00")
        self.assertTrue(timezone.is_aware(dt))
        self.assertEqual((dt.year, dt.month, dt.day, dt.hour), (2026, 9, 7, 8))

    def test_iso_with_offset_keeps_offset(self):
        dt = to_aware_datetime("2026-09-07T08:00:00+02:00")
        self.assertTrue(timezone.is_aware(dt))
        self.assertEqual(dt.utcoffset().total_seconds(), 2 * 3600)

    def test_zulu_stays_aware(self):
        dt = to_aware_datetime("2026-09-07T06:00:00Z")
        self.assertTrue(timezone.is_aware(dt))

    def test_date_only_becomes_midnight_aware(self):
        dt = to_aware_datetime("2026-09-07")
        self.assertTrue(timezone.is_aware(dt))
        self.assertEqual(dt.hour, 0)

    def test_already_aware_datetime_unchanged(self):
        original = datetime(2026, 9, 7, 8, 0, tzinfo=dt_timezone.utc)
        self.assertEqual(to_aware_datetime(original), original)


class MapMincutDatesTest(TestCase):
    def test_maps_forecast_and_exec_separately(self):
        mapped = map_mincut_to_supply_cut_dates({
            "forecast_start": "2026-09-20 08:00:00",
            "forecast_end": "2026-09-20 14:00:00",
            "exec_start": "2026-09-20 08:15:00",
            "exec_end": "2026-09-20 13:50:00",
            "received_date": "2025-11-10",
        })
        self.assertEqual(
            (mapped["date_start"].year, mapped["date_start"].month, mapped["date_start"].day, mapped["date_start"].hour),
            (2026, 9, 20, 8),
        )
        self.assertEqual(mapped["exec_start"].minute, 15)
        self.assertEqual(mapped["exec_end"].minute, 50)
        self.assertEqual(mapped["date_end"].hour, 14)

    def test_empty_mincut_is_valid_and_ignores_received_date(self):
        mapped = map_mincut_to_supply_cut_dates({
            "forecast_start": None,
            "forecast_end": None,
            "exec_start": None,
            "exec_end": None,
            "received_date": "2025-11-10",
        })
        self.assertIsNone(mapped["date_start"])
        self.assertIsNone(mapped["date_end"])
        self.assertIsNone(mapped["exec_start"])
        self.assertIsNone(mapped["exec_end"])
        self.assertEqual(set(mapped), {"date_start", "date_end", "exec_start", "exec_end"})
