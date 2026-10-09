from unittest.mock import patch

from django.contrib.auth.models import User
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from contract.models import Contract, ContractRequest
from coredata.models import ConfigProject
from documentmanager.models import Document, DocumentSign
from integrations.outbound.signing.exceptions import SigningApiError


class DocumentSignApiTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_superuser(
            username="docsign", email="docsign@example.com", password="secret"
        )
        self.client.force_authenticate(user=self.user)
        ConfigProject.objects.filter(token="DOCUMENT_SIGN_ENABLED").update(value="true")
        if not ConfigProject.objects.filter(token="DOCUMENT_SIGN_ENABLED").exists():
            ConfigProject.objects.create(token="DOCUMENT_SIGN_ENABLED", value="true")
        ConfigProject.objects.get_or_create(
            token="contract_terminated_status", defaults={"value": "-1"}
        )
        self.contract_request = ContractRequest.objects.create(token="SOL-1")
        self.contract = Contract.objects.create(token="260929006")
        self.original = Document.objects.create(
            entity_id=1, service="hdd", document_name="original.pdf"
        )
        self.signed = Document.objects.create(
            entity_id=1, service="hdd", document_name="signed.pdf"
        )

    def _document_sign(self, **overrides):
        data = {
            "contract_request": self.contract_request,
            "contract_file": self.original,
            "status": DocumentSign.STATUS_SENDED,
            "token": "550e8400-e29b-41d4-a716-446655440000",
            "otp_name": "Nom Cognom",
            "otp_email": "info@example.com",
            "otp_phone": "679000000",
        }
        data.update(overrides)
        return DocumentSign.objects.create(**data)

    def test_create_stays_pending_and_does_not_call_sign(self):
        with patch(
            "integrations.outbound.signing.services.create_document_sign_session"
        ) as mock_send:
            response = self.client.post(
                reverse("documentsign-list"),
                {
                    "contract_request": self.contract_request.id,
                    "contract_file": self.original.id,
                    "otp_name": "Nom Cognom",
                    "otp_email": "info@example.com",
                    "otp_phone": "679000000",
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], DocumentSign.STATUS_PENDING)
        self.assertIsNone(response.data["contract_file_signed_url"])
        mock_send.assert_not_called()

    def test_create_requires_contract_or_request(self):
        response = self.client.post(
            reverse("documentsign-list"),
            {"otp_name": "Albert", "otp_email": "a@b.c"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_by_contract_finds_request_migrated_to_contract(self):
        document_sign = self._document_sign(contract=self.contract)
        response = self.client.get(
            reverse("document_signs_by_contract"),
            {"contract_id": self.contract.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["document_signs"]), 1)
        row = response.data["document_signs"][0]
        self.assertEqual(row["id"], document_sign.id)
        self.assertEqual(row["contract"], self.contract.id)
        self.assertEqual(row["contract_request"], self.contract_request.id)
        self.assertEqual(row["contract_token"], "260929006")
        self.assertEqual(row["contract_request_token"], "SOL-1")
        self.assertIsNone(row["contract_file_signed_url"])

    @patch("documentmanager.views.download_document")
    def test_download_does_not_serve_original_before_signed(self, mock_download):
        document_sign = self._document_sign(contract_file_signed=self.signed)
        response = self.client.get(reverse("document_sign_download", args=[document_sign.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        mock_download.assert_not_called()

    @patch("documentmanager.views.download_document")
    def test_download_serves_signed_pdf_only(self, mock_download):
        mock_download.return_value = HttpResponse(b"%PDF-signed", content_type="application/octet-stream")
        document_sign = self._document_sign(
            status=DocumentSign.STATUS_SIGNED,
            contract_file_signed=self.signed,
            signed_at=timezone.now(),
        )
        response = self.client.get(reverse("document_sign_download", args=[document_sign.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn('filename="signed.pdf"', response["Content-Disposition"])
        self.assertEqual(response.content, b"%PDF-signed")
        self.assertEqual(mock_download.call_args.args[0].id, self.signed.id)

    @patch("integrations.outbound.signing.polling.retrieve_signed_document")
    def test_retrieve_pending_returns_json_and_keeps_status(self, mock_retrieve):
        mock_retrieve.return_value = {"action": "pending"}
        document_sign = self._document_sign()
        response = self.client.post(reverse("documentsign-retrieve", args=[document_sign.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response.data["status"], DocumentSign.STATUS_SENDED)
        self.assertIsNone(response.data["contract_file_signed_url"])
        self.assertIn(
            f"/documentmanager/view-document/{self.original.id}/",
            response.data["contract_file_url"],
        )

    @patch("integrations.outbound.signing.polling.retrieve_signed_document")
    def test_retrieve_signed_returns_updated_object(self, mock_retrieve):
        document_sign = self._document_sign()

        def _sign(obj):
            obj.status = DocumentSign.STATUS_SIGNED
            obj.contract_file_signed = self.signed
            obj.signed_at = timezone.now()
            obj.save()
            return {"action": "signed"}

        mock_retrieve.side_effect = _sign
        response = self.client.post(reverse("documentsign-retrieve", args=[document_sign.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], DocumentSign.STATUS_SIGNED)
        self.assertIn(
            f"/document-sign-download/{document_sign.id}/",
            response.data["contract_file_signed_url"],
        )
        self.assertIsNotNone(response.data["signed_at"])

    @patch("integrations.outbound.signing.polling.retrieve_signed_document")
    def test_retrieve_remote_failure_marks_error(self, mock_retrieve):
        document_sign = self._document_sign()

        def _fail(obj):
            obj.status = DocumentSign.STATUS_ERROR
            obj.error_report = "timeout"
            obj.save()
            raise SigningApiError("timeout")

        mock_retrieve.side_effect = _fail
        response = self.client.post(reverse("documentsign-retrieve", args=[document_sign.id]))
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(response.data["status"], DocumentSign.STATUS_ERROR)
        self.assertEqual(response.data["error_report"], "timeout")

    @patch("integrations.outbound.signing.polling.retrieve_signed_document")
    def test_retrieve_rejects_pending_local(self, mock_retrieve):
        document_sign = self._document_sign(status=DocumentSign.STATUS_PENDING, token=None)
        response = self.client.post(reverse("documentsign-retrieve", args=[document_sign.id]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_retrieve.assert_not_called()
        document_sign.refresh_from_db()
        self.assertEqual(document_sign.status, DocumentSign.STATUS_PENDING)

    def test_delete_removes_the_request(self):
        document_sign = self._document_sign(status=DocumentSign.STATUS_SIGNED)
        response = self.client.delete(reverse("documentsign-detail", args=[document_sign.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(DocumentSign.objects.filter(id=document_sign.id).exists())

    def test_retrieve_requires_authentication(self):
        document_sign = self._document_sign()
        self.client.force_authenticate(user=None)
        response = self.client.post(reverse("documentsign-retrieve", args=[document_sign.id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
