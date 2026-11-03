from datetime import datetime, timezone as dt_timezone

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from integrations.models import (
    IntegrationRequestLog,
    SendBatch,
    SendBatchStatus,
    SendBatchType,
)


@override_settings(ODOO_INBOUND_BEARER_TOKEN="test-odoo-inbound-token")
class OdooBatchResultInboundTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("odoo-inbound-batch-results")
        from integrations.models import SendBatchProvider

        provider = SendBatchProvider.objects.get_or_create(
            token="odoo",
            defaults={"name": "Odoo", "position": 1, "is_default": True},
        )[0]
        self.batch_type = SendBatchType.objects.get_or_create(
            provider=provider,
            token="invoices",
            defaults={
                "name": "Invoices",
                "endpoint": "/batch/invoices",
                "position": 1,
                "is_default": True,
            },
        )[0]
        self.status_pending = SendBatchStatus.objects.get_or_create(
            token="0",
            defaults={
                "name": "Pendent",
                "color": "yellow",
                "position": 1,
                "is_default": True,
            },
        )[0]
        self.status_processing = SendBatchStatus.objects.get_or_create(
            token="1",
            defaults={
                "name": "En procés",
                "color": "sky",
                "position": 2,
                "is_default": False,
            },
        )[0]
        self.status_finalized = SendBatchStatus.objects.get_or_create(
            token="2",
            defaults={"name": "Finalitzat", "color": "green", "position": 3},
        )[0]
        self.batch = SendBatch.objects.create(
            token="FACT-202610-001",
            batch_type=self.batch_type,
            status=self.status_processing,
        )
        self.payload = {
            "batch_id": "FACT-202610-001",
            "type": "invoices",
            "status": "done",
            "received_at": "2026-10-21T13:04:00Z",
            "finished_at": "2026-10-21T13:08:12Z",
            "summary": {
                "total": 2,
                "ok": 1,
                "duplicate_ignored": 0,
                "error": 1,
                "pending": 0,
            },
            "results": [
                {
                    "aqua_id": "01000028192",
                    "odoo_id": 442,
                    "status": "ok",
                    "message": None,
                },
                {
                    "aqua_id": "01000028193",
                    "odoo_id": None,
                    "status": "error",
                    "message": "Payment mode with code 'CASH' not found",
                },
            ],
        }

    def _auth_headers(self, token="test-odoo-inbound-token"):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_rejects_missing_bearer(self):
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.batch.refresh_from_db()
        self.assertIsNone(self.batch.final_response)

    def test_rejects_wrong_bearer(self):
        response = self.client.post(
            self.url, self.payload, format="json", **self._auth_headers("wrong")
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_applies_final_result(self):
        response = self.client.post(
            self.url, self.payload, format="json", **self._auth_headers()
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["accepted"])
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status_id, self.status_finalized.id)
        self.assertEqual(self.batch.summary["error"], 1)
        self.assertEqual(len(self.batch.final_response["results"]), 2)
        self.assertTrue(
            IntegrationRequestLog.objects.filter(
                provider="odoo",
                direction=IntegrationRequestLog.DIRECTION_INBOUND,
                success=True,
                object_id="FACT-202610-001",
            ).exists()
        )

    def test_unknown_batch_returns_404(self):
        payload = {**self.payload, "batch_id": "UNKNOWN-BATCH"}
        response = self.client.post(
            self.url, payload, format="json", **self._auth_headers()
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_ignores_stale_finished_at(self):
        self.batch.finished_at = datetime(2026, 10, 21, 14, 0, 0, tzinfo=dt_timezone.utc)
        self.batch.status = self.status_finalized
        self.batch.final_response = {"batch_id": "FACT-202610-001", "status": "done"}
        self.batch.save()

        response = self.client.post(
            self.url, self.payload, format="json", **self._auth_headers()
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["accepted"])
        self.assertEqual(response.data["reason"], "stale_finished_at")
