import base64
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from contract.models import ContractRequest
from integrations.models import ContractSigningSession, IntegrationRequestLog

CALLBACK_SETTINGS = {
    "SIGN_CALLBACK_API_KEY": "test-callback-key",
}


@override_settings(**CALLBACK_SETTINGS)
class SigningCallbackViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("signing-callback")
        self.contract_request = ContractRequest.objects.create(token="TEST-001")
        self.auth_headers = {"HTTP_X_API_KEY": "test-callback-key"}

    def _base_payload(self, **overrides):
        payload = {
            "event": "session.signed",
            "external_reference": self.contract_request.token,
            "session_id": "550e8400-e29b-41d4-a716-446655440000",
            "signed_at": "2026-06-25T14:30:00+02:00",
        }
        payload.update(overrides)
        return payload

    def test_callback_rejects_missing_api_key(self):
        response = self.client.post(self.url, self._base_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_callback_rejects_unsupported_event(self):
        response = self.client.post(
            self.url,
            self._base_payload(event="session.viewed"),
            format="json",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_callback_marks_session_as_expired(self):
        session = ContractSigningSession.objects.create(
            contract_request=self.contract_request,
            session_id="550e8400-e29b-41d4-a716-446655440000",
            external_reference=self.contract_request.token,
            status=ContractSigningSession.STATUS_PENDING,
            signing_url="https://sign.example.com/s/abc/",
            recipient_name="Anna Garcia",
            recipient_email="anna@example.com",
        )

        response = self.client.post(
            self.url,
            self._base_payload(event="session.expired"),
            format="json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["ok"])
        session.refresh_from_db()
        self.assertEqual(session.status, ContractSigningSession.STATUS_EXPIRED)

    def test_callback_updates_session_to_signed(self):
        session = ContractSigningSession.objects.create(
            contract_request=self.contract_request,
            session_id="550e8400-e29b-41d4-a716-446655440000",
            external_reference=self.contract_request.token,
            status=ContractSigningSession.STATUS_PENDING,
            signing_url="https://sign.example.com/s/abc/",
            recipient_name="Anna Garcia",
            recipient_email="anna@example.com",
        )

        response = self.client.post(
            self.url, self._base_payload(), format="json", **self.auth_headers
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["ok"])
        self.assertFalse(response.data["contract_file_saved"])
        session.refresh_from_db()
        self.assertEqual(session.status, ContractSigningSession.STATUS_SIGNED)
        self.assertIsNotNone(session.signed_at)

        log = IntegrationRequestLog.objects.get(provider="signing", direction="inbound")
        self.assertTrue(log.success)

    @patch("integrations.inbound.signing.services.SigningClient.download_signed_document")
    @patch("integrations.inbound.signing.services.save_signed_contract_file")
    def test_callback_saves_signed_document(self, mock_save, mock_download):
        mock_download.return_value = b"%PDF-1.4 signed"
        ContractSigningSession.objects.create(
            contract_request=self.contract_request,
            session_id="550e8400-e29b-41d4-a716-446655440001",
            external_reference=self.contract_request.token,
            status=ContractSigningSession.STATUS_PENDING,
            signing_url="https://sign.example.com/s/abc/",
            recipient_name="Anna Garcia",
            recipient_email="anna@example.com",
        )

        response = self.client.post(
            self.url,
            self._base_payload(
                session_id="550e8400-e29b-41d4-a716-446655440001",
                documents=[{"id": 1, "signed": True}],
            ),
            format="json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["contract_file_saved"])
        mock_download.assert_called_once_with("550e8400-e29b-41d4-a716-446655440001", 1)
        mock_save.assert_called_once_with(self.contract_request, b"%PDF-1.4 signed")

    def test_callback_idempotent_when_already_signed(self):
        ContractSigningSession.objects.create(
            contract_request=self.contract_request,
            session_id="550e8400-e29b-41d4-a716-446655440000",
            external_reference=self.contract_request.token,
            status=ContractSigningSession.STATUS_SIGNED,
            signing_url="https://sign.example.com/s/abc/",
            recipient_name="Anna Garcia",
            recipient_email="anna@example.com",
        )

        response = self.client.post(
            self.url, self._base_payload(), format="json", **self.auth_headers
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["already_processed"])

    def test_callback_unknown_contract_request(self):
        response = self.client.post(
            self.url,
            self._base_payload(external_reference="UNKNOWN-999"),
            format="json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
