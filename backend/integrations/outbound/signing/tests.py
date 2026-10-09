from unittest.mock import MagicMock, patch

import requests
from django.test import TestCase, override_settings

from integrations.models import ContractSigningSession, IntegrationRequestLog
from integrations.outbound.signing.client import SigningClient
from integrations.outbound.signing.exceptions import SigningApiError


@override_settings(
    SIGNING_BASE_URL="https://sign.example.com",
    SIGNING_API_KEY="test-api-key",
    SIGNING_TIMEOUT=10,
)
class SigningClientTest(TestCase):
    @patch("integrations.outbound.signing.client.requests.post")
    def test_create_session_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "pending",
            "signing_url": "https://sign.example.com/s/abc/",
            "email_sent": True,
        }
        mock_post.return_value = mock_response

        client = SigningClient()
        result = client.create_session(
            recipient_name="Anna Garcia",
            recipient_email="anna@example.com",
            documents=[("contracte.pdf", b"%PDF-1.4", "application/pdf")],
            external_reference="42",
            callback_url="https://customers.example.com/api/signing/callback/",
        )

        self.assertEqual(result["id"], "550e8400-e29b-41d4-a716-446655440000")
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(
            call_kwargs["headers"]["X-API-Key"],
            "test-api-key",
        )
        self.assertEqual(call_kwargs["data"]["recipient_email"], "anna@example.com")

        log = IntegrationRequestLog.objects.get()
        self.assertEqual(log.provider, "signing")
        self.assertTrue(log.success)
        self.assertEqual(log.status_code, 201)

    @patch("integrations.outbound.signing.client.requests.post")
    def test_create_session_http_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        client = SigningClient()
        with self.assertRaises(SigningApiError):
            client.create_session(
                recipient_name="Anna Garcia",
                recipient_email="anna@example.com",
                documents=[("contracte.pdf", b"%PDF-1.4", "application/pdf")],
            )

        log = IntegrationRequestLog.objects.get()
        self.assertFalse(log.success)

    @patch("integrations.outbound.signing.client.requests.post")
    def test_create_session_connection_error(self, mock_post):
        mock_post.side_effect = requests.RequestException("Connection failed")

        client = SigningClient()
        with self.assertRaises(SigningApiError):
            client.create_session(
                recipient_name="Anna Garcia",
                recipient_email="anna@example.com",
                documents=[("contracte.pdf", b"%PDF-1.4", "application/pdf")],
            )

        log = IntegrationRequestLog.objects.get()
        self.assertFalse(log.success)

    def _probe_response(self, *, status_code, body=None, content_type="application/json", text=""):
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.headers = {"Content-Type": content_type}
        mock_response.text = text
        if body is None:
            mock_response.json.side_effect = ValueError("not json")
        else:
            mock_response.json.return_value = body
        return mock_response

    @patch("integrations.outbound.signing.client.requests.get")
    def test_check_connection_accepts_authenticated_404(self, mock_get):
        mock_get.return_value = self._probe_response(
            status_code=404, body={"detail": "Not found."}
        )

        result = SigningClient().check_connection()

        self.assertTrue(result["ok"])
        self.assertEqual(result["status_code"], 404)
        mock_get.assert_called_once()
        self.assertEqual(mock_get.call_args.kwargs["headers"]["X-API-Key"], "test-api-key")
        self.assertIn(
            "/api/sessions/00000000-0000-0000-0000-000000000000/",
            mock_get.call_args.args[0],
        )

        log = IntegrationRequestLog.objects.get()
        self.assertTrue(log.success)
        self.assertEqual(log.status_code, 404)
        self.assertEqual(log.object_type, "connection_check")

    @patch("integrations.outbound.signing.client.requests.get")
    def test_check_connection_rejects_invalid_api_key(self, mock_get):
        mock_get.return_value = self._probe_response(
            status_code=403, body={"detail": "API key no vàlida."}
        )

        with self.assertRaises(SigningApiError) as caught:
            SigningClient().check_connection()

        self.assertIn("API key", str(caught.exception))
        log = IntegrationRequestLog.objects.get()
        self.assertFalse(log.success)
        self.assertEqual(log.status_code, 403)

    @patch("integrations.outbound.signing.client.requests.get")
    def test_check_connection_rejects_html_404(self, mock_get):
        mock_get.return_value = self._probe_response(
            status_code=404,
            content_type="text/html",
            text="<html>not found</html>",
        )

        with self.assertRaises(SigningApiError):
            SigningClient().check_connection()

        log = IntegrationRequestLog.objects.get()
        self.assertFalse(log.success)

    @patch("integrations.outbound.signing.client.requests.get")
    def test_check_connection_connection_error(self, mock_get):
        mock_get.side_effect = requests.RequestException("Connection failed")

        with self.assertRaises(SigningApiError):
            SigningClient().check_connection()

        log = IntegrationRequestLog.objects.get()
        self.assertFalse(log.success)


class DocumentSignRetrieveTest(TestCase):
    def setUp(self):
        from contract.models import ContractRequest
        from documentmanager.models import DocumentSign

        self.DocumentSign = DocumentSign
        self.contract_request = ContractRequest.objects.create(token="SOL-RETR")
        self.document_sign = DocumentSign.objects.create(
            contract_request=self.contract_request,
            status=DocumentSign.STATUS_SENDED,
            token="550e8400-e29b-41d4-a716-446655440000",
            otp_name="Anna",
            otp_email="anna@example.com",
        )

    def test_pending_remote_does_not_download_or_change_status(self):
        from integrations.outbound.signing.polling import retrieve_signed_document

        client = MagicMock()
        client.get_session.return_value = {"status": "pending", "documents": []}
        result = retrieve_signed_document(self.document_sign, client=client)

        self.assertEqual(result["action"], "pending")
        client.download_signed_document.assert_not_called()
        self.document_sign.refresh_from_db()
        self.assertEqual(self.document_sign.status, self.DocumentSign.STATUS_SENDED)

    @patch("integrations.outbound.signing.polling.save_signed_document_sign_file")
    def test_signed_remote_saves_pdf(self, mock_save):
        from integrations.outbound.signing.polling import retrieve_signed_document

        client = MagicMock()
        client.get_session.return_value = {
            "status": "signed",
            "signed_at": "2026-09-30T10:00:00+02:00",
            "documents": [{"id": 7, "signed": True}],
        }
        client.download_signed_document.return_value = b"%PDF-signed"
        result = retrieve_signed_document(self.document_sign, client=client)

        self.assertEqual(result["action"], "signed")
        client.download_signed_document.assert_called_once()
        mock_save.assert_called_once()
        self.assertEqual(mock_save.call_args.args[1], b"%PDF-signed")

    def test_expired_remote_marks_expired(self):
        from integrations.outbound.signing.polling import retrieve_signed_document

        client = MagicMock()
        client.get_session.return_value = {"status": "expired"}
        result = retrieve_signed_document(self.document_sign, client=client)

        self.assertEqual(result["action"], "expired")
        client.download_signed_document.assert_not_called()
        self.document_sign.refresh_from_db()
        self.assertEqual(self.document_sign.status, self.DocumentSign.STATUS_EXPIRED)
        self.assertIsNone(self.document_sign.error_report)

    def test_remote_error_marks_error_and_raises(self):
        from integrations.outbound.signing.polling import retrieve_signed_document

        client = MagicMock()
        client.get_session.side_effect = SigningApiError("Aqua360 no respon")
        with self.assertRaises(SigningApiError):
            retrieve_signed_document(self.document_sign, client=client)

        self.document_sign.refresh_from_db()
        self.assertEqual(self.document_sign.status, self.DocumentSign.STATUS_ERROR)
        self.assertIn("Aqua360 no respon", self.document_sign.error_report)

    def test_poll_still_swallows_errors(self):
        from integrations.outbound.signing.polling import poll_document_sign

        client = MagicMock()
        client.get_session.side_effect = SigningApiError("timeout")
        result = poll_document_sign(self.document_sign, client=client)

        self.assertEqual(result["action"], "error")
        self.document_sign.refresh_from_db()
        self.assertEqual(self.document_sign.status, self.DocumentSign.STATUS_SENDED)


@override_settings(
    SIGNING_BASE_URL="https://sign.example.com",
    SIGNING_API_KEY="test-api-key",
    SIGNING_CALLBACK_URL="https://customers.example.com/signing/callback/",
)
class DocumentSignResendTest(TestCase):
    @patch("integrations.outbound.signing.services.is_document_sign_enabled", return_value=True)
    @patch("integrations.outbound.signing.services.download_document")
    @patch("integrations.outbound.signing.services.SigningClient")
    def test_successful_resend_unlinks_previous_signed_file(
        self, mock_client_cls, mock_download, _enabled
    ):
        from contract.models import ContractRequest
        from documentmanager.models import Document, DocumentSign
        from integrations.outbound.signing.services import create_document_sign_session

        content = MagicMock()
        content.getvalue.return_value = b"%PDF-original"
        mock_download.return_value = content
        mock_client_cls.return_value.create_session.return_value = {
            "id": "new-session-id",
            "email_sent": True,
        }

        contract_request = ContractRequest.objects.create(token="SOL-RESEND")
        original = Document.objects.create(entity_id=1, service="hdd", document_name="original.pdf")
        signed = Document.objects.create(entity_id=1, service="hdd", document_name="signed.pdf")
        document_sign = DocumentSign.objects.create(
            contract_request=contract_request,
            status=DocumentSign.STATUS_SIGNED,
            contract_file=original,
            contract_file_signed=signed,
            token="old-session",
            otp_name="Anna",
            otp_email="anna@example.com",
        )

        create_document_sign_session(document_sign, force=True)
        document_sign.refresh_from_db()

        self.assertEqual(document_sign.status, DocumentSign.STATUS_SENDED)
        self.assertEqual(document_sign.token, "new-session-id")
        self.assertIsNone(document_sign.contract_file_signed_id)
        self.assertIsNone(document_sign.signed_at)
