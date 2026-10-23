import base64
import zipfile
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from coredata.models import ConfigProject, Person
from contract.models import Contract, ContractStatus
from billing.models import Invoice
from documentmanager.models import Document

SLASH_TOKEN = "12345678/001"
PLAIN_TOKEN = "12345678"
HOLDER_TOKEN = "12345678Z"


class ContractOVViewTests(TestCase):
    """`GET /ov/contract-detail/` responde directamente (200), sense redirect.

    El token pot contenir barra (`/`), que una ruta `<str:token>` no pot
    resoldre: abans del fix això provocava `NoReverseMatch` (500).
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="ov-contract-detail-test", password="not-used"
        )
        # `ContractFullDetailSerializer.get_termination_date` i el signal
        # `terminate_contract_update_bail` fan servir aquests paràmetres.
        for token, value in (
            ("contract_termination_completed_token", "3"),
            ("contract_terminated_status", "-1"),
        ):
            if not ConfigProject.objects.filter(token=token).exists():
                ConfigProject.objects.create(token=token, value=value)

        cls.status = ContractStatus.objects.create(token="1", name="Active")
        cls.holder = Person.objects.create(
            token=HOLDER_TOKEN, name="Test", surname="Holder"
        )
        cls.slash_contract = Contract.objects.create(
            token=SLASH_TOKEN, status=cls.status, holder=cls.holder
        )
        cls.plain_contract = Contract.objects.create(
            token=PLAIN_TOKEN, status=cls.status, holder=cls.holder
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_slash_token_returns_200_with_contract_data(self):
        response = self.client.get(
            reverse("contract-ov"), {"contract_token": SLASH_TOKEN}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get("Location"))
        self.assertEqual(response.data["token"], SLASH_TOKEN)
        self.assertEqual(response.data["status_token"], "1")
        self.assertEqual(response.data["holder_token"], HOLDER_TOKEN)

    def test_plain_token_returns_200(self):
        response = self.client.get(
            reverse("contract-ov"), {"contract_token": PLAIN_TOKEN}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get("Location"))
        self.assertEqual(response.data["token"], PLAIN_TOKEN)

    def test_unknown_token_returns_404_without_redirect(self):
        response = self.client.get(
            reverse("contract-ov"), {"contract_token": "99999999/999"}
        )

        self.assertEqual(response.status_code, 404)
        self.assertIsNone(response.get("Location"))
        self.assertEqual(response.data["error"], "Contract not found")

    def test_missing_contract_token_returns_400(self):
        response = self.client.get(reverse("contract-ov"))

        self.assertEqual(response.status_code, 400)
        self.assertIsNone(response.get("Location"))
        self.assertEqual(
            response.data["error"], "Contract token is required"
        )

    def test_extra_query_params_are_processed_in_the_same_response(self):
        """El `dni` arriba al serialitzador (mateixa resposta, sense 302)."""
        response = self.client.get(
            reverse("contract-ov"),
            {"contract_token": SLASH_TOKEN, "dni": HOLDER_TOKEN},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get("Location"))
        self.assertIn("is_account_holder", response.data)
        self.assertFalse(response.data["is_account_holder"])


class InvoicePdfReuseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="ov-invoice-pdf-test")
        for token, value in (
            ("invoice_type_invoice_token", "INVOICE"),
            ("contract_termination_completed_token", "3"),
            ("contract_terminated_status", "-1"),
            ("invoice_status_paid_token", "0"),
            ("invoice_status_cancelled_token", "-1"),
        ):
            ConfigProject.objects.create(token=token, value=value)
        cls.contract = Contract.objects.create(token="OV-PDF-CONTRACT")
        cls.invoice_one = Invoice.objects.create(
            token="OV-PDF-001",
            contract=cls.contract,
            type_final="INVOICE",
            serie_final="2026/001",
        )
        cls.invoice_two = Invoice.objects.create(
            token="OV-PDF-002",
            contract=cls.contract,
            type_final="INVOICE",
            serie_final="2026/002",
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _document(self, invoice, name="invoice.pdf"):
        return Document.objects.create(
            entity="FACTURES",
            field="FACTURA",
            entity_id=invoice.id,
            document_name=name,
            service="hdd",
        )

    def _invoice_pdf_url(self, token):
        return reverse("invoice-pdf-ov"), {
            "contract_token": self.contract.token,
            "invoice_token": token,
        }

    def _batch_response(self, tokens):
        return self.client.post(
            f"{reverse('batch-invoice-download-ov')}?contract_token={self.contract.token}",
            {"invoice_tokens": tokens},
            format="json",
        )

    def _zip_entries(self, response):
        payload = b"".join(response.streaming_content)
        with zipfile.ZipFile(BytesIO(payload), "r") as zip_file:
            return {
                name: zip_file.read(name)
                for name in zip_file.namelist()
            }

    def test_single_endpoint_reuses_stored_pdf(self):
        document = self._document(self.invoice_one)
        self.invoice_one.invoice_file = document
        self.invoice_one.save(update_fields=["invoice_file"])
        stored_pdf = b"%PDF-stored-single"

        with patch(
            "ov.views.download_document",
            return_value=HttpResponse(stored_pdf),
        ) as download, patch(
            "ov.views.generate_report_invoice_pdf"
        ) as generate:
            response = self.client.get(
                *self._invoice_pdf_url(self.invoice_one.token)
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(base64.b64decode(response.data["pdf"]), stored_pdf)
        self.assertEqual(response.data["document_name"], document.document_name)
        download.assert_called_once_with(document)
        generate.assert_not_called()

    def test_single_endpoint_generates_when_document_is_missing(self):
        generated_pdf = b"%PDF-generated-single"
        with patch(
            "ov.views.generate_report_invoice_pdf",
            return_value=(None, None, BytesIO(generated_pdf)),
        ) as generate:
            response = self.client.get(
                *self._invoice_pdf_url(self.invoice_one.token)
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(base64.b64decode(response.data["pdf"]), generated_pdf)
        generate.assert_called_once()

    def test_single_endpoint_generates_when_stored_pdf_retrieval_fails(self):
        document = self._document(self.invoice_one)
        self.invoice_one.invoice_file = document
        self.invoice_one.save(update_fields=["invoice_file"])
        generated_pdf = b"%PDF-generated-after-retrieval-error"

        with patch(
            "ov.views.download_document",
            side_effect=OSError("stored PDF unavailable"),
        ) as download, patch(
            "ov.views.generate_report_invoice_pdf",
            return_value=(None, None, BytesIO(generated_pdf)),
        ) as generate:
            response = self.client.get(
                *self._invoice_pdf_url(self.invoice_one.token)
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(base64.b64decode(response.data["pdf"]), generated_pdf)
        download.assert_called_once_with(document)
        generate.assert_called_once()

    def test_batch_endpoint_reuses_stored_pdfs(self):
        document_one = self._document(self.invoice_one, "invoice-one.pdf")
        document_two = self._document(self.invoice_two, "invoice-two.pdf")
        self.invoice_one.invoice_file = document_one
        self.invoice_two.invoice_file = document_two
        Invoice.objects.bulk_update(
            [self.invoice_one, self.invoice_two], ["invoice_file"]
        )
        stored_pdfs = {
            document_one.id: b"%PDF-stored-one",
            document_two.id: b"%PDF-stored-two",
        }

        def download(document):
            return HttpResponse(stored_pdfs[document.id])

        with patch("ov.views.download_document", side_effect=download) as mocked, patch(
            "ov.views.generate_report_invoice_pdf"
        ) as generate:
            response = self._batch_response(
                [self.invoice_one.token, self.invoice_two.token]
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self._zip_entries(response),
            {
                "factura_2026-001.pdf": b"%PDF-stored-one",
                "factura_2026-002.pdf": b"%PDF-stored-two",
            },
        )
        self.assertEqual(mocked.call_count, 2)
        generate.assert_not_called()

    def test_batch_endpoint_generates_when_document_is_missing(self):
        generated_pdf = b"%PDF-generated-batch"
        with patch(
            "ov.views.generate_report_invoice_pdf",
            return_value=(None, None, BytesIO(generated_pdf)),
        ) as generate:
            response = self._batch_response([self.invoice_one.token])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self._zip_entries(response),
            {"factura_2026-001.pdf": generated_pdf},
        )
        generate.assert_called_once()
        self.assertFalse(generate.call_args.kwargs["save_pdf"])

    def test_batch_endpoint_generates_when_one_retrieval_fails(self):
        document = self._document(self.invoice_one)
        self.invoice_one.invoice_file = document
        self.invoice_one.save(update_fields=["invoice_file"])
        stored_pdf = b"%PDF-stored-batch"
        generated_pdf = b"%PDF-generated-after-retrieval-error"

        def download(document):
            if document.id == self.invoice_one.invoice_file_id:
                return HttpResponse(stored_pdf)
            raise OSError("stored PDF unavailable")

        with patch("ov.views.download_document", side_effect=download), patch(
            "ov.views.generate_report_invoice_pdf",
            return_value=(None, None, BytesIO(generated_pdf)),
        ) as generate:
            response = self._batch_response(
                [self.invoice_one.token, self.invoice_two.token]
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self._zip_entries(response),
            {
                "factura_2026-001.pdf": stored_pdf,
                "factura_2026-002.pdf": generated_pdf,
            },
        )
        generate.assert_called_once()
        self.assertFalse(generate.call_args.kwargs["save_pdf"])
