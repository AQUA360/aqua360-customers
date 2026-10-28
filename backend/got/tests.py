import json
import os
import tempfile
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from documentmanager.models import Document
from got.models import OrderForm
from lecturapp.models import ReadingOperator, Token
from order.models import Operator, Order, OrderReport, OrderReportDocument, OrderStatus, OrderType


class ViewDocumentFlowTest(TestCase):
    """
    Flux complet del GOT (login, foto de formulari, informe, adjunt i llistat d'informes):
    tots els documents que mostra el GOT es poden descarregar amb el token de l'operari,
    i cap document es pot descarregar sense token ni fora del context de les ordres.
    """

    def setUp(self):
        self.storage = tempfile.TemporaryDirectory()
        self.addCleanup(self.storage.cleanup)
        settings_override = override_settings(
            DOCUMENT_STORAGE_PATH=self.storage.name,
            DOCUMENT_MANAGER_SERVICES={"order": "hdd"},
        )
        settings_override.enable()
        self.addCleanup(settings_override.disable)

        self.reading_operator = ReadingOperator.objects.create(
            name="Op", surname="Test", username="op-got", password="pwd-got"
        )
        self.operator = Operator.objects.create(name="Op", app_user=self.reading_operator)

        order_type = OrderType.objects.create(token="got_test", name="Ordre GOT")
        OrderForm.objects.create(
            name="Formulari",
            order_type=order_type,
            structure=[
                {"token": "lectura", "name": "Lectura", "type": "number", "required": True},
                {"token": "foto", "name": "Foto", "type": "photo", "required": True},
            ],
        )
        status = OrderStatus.objects.create(token="5", name="En curs")
        self.order = Order.objects.create(token="OT-GOT-1", type=order_type, status=status)
        self.order.operators.add(self.operator)

        self.token = self._login()

    # --- utilitats ---------------------------------------------------------------

    def _login(self):
        response = self.client.post(
            "/got/auth/login/",
            json.dumps({"username": "op-got", "password": "pwd-got"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["token"]

    def _headers(self, token=None):
        token = self.token if token is None else token
        return {"HTTP_X_APP_TOKEN": token} if token else {}

    def _view(self, document_id, token=None):
        return self.client.get(f"/got/orders/view-document/{document_id}/", **self._headers(token))

    def _file_document(self, entity, name, content=b"contingut", **fields):
        path = os.path.join(self.storage.name, name)
        with open(path, "wb") as f:
            f.write(content)
        return Document.objects.create(
            entity=entity, entity_id=1, service="hdd", document_name=name, location=path, **fields
        )

    def _upload_form_photo(self):
        response = self.client.post(
            f"/got/orders/{self.order.id}/upload-form-photo/",
            {"file": SimpleUploadedFile("foto.jpg", b"foto-formulari"), "field_token": "foto"},
            **self._headers(),
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def _add_report(self, photo_id):
        response = self.client.post(
            f"/got/orders/{self.order.id}/add-report/",
            json.dumps({
                "start_at": "08:00",
                "end_at": "09:00",
                "observation": "Informe de prova",
                "filled_form": [
                    {"token": "lectura", "response": 123},
                    {"token": "foto", "response": photo_id},
                ],
            }),
            content_type="application/json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, 201, response.content)
        return OrderReport.objects.get(order=self.order)

    def _add_report_document(self, report):
        response = self.client.post(
            f"/got/orders/{self.order.id}/reports/{report.id}/add-document/",
            {"file": SimpleUploadedFile("adjunt.pdf", b"adjunt-informe")},
            **self._headers(),
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["document"]

    def _documents_shown_in_reports(self):
        """Ids de document que el frontend del GOT demana a `view-document` (ReportsList.vue)."""
        response = self.client.get(f"/got/orders/{self.order.id}/reports/", **self._headers())
        self.assertEqual(response.status_code, 200, response.content)
        ids = set()

        def collect(value):
            if isinstance(value, dict):
                if value.get("type") == "photo" and str(value.get("response") or "").isdigit():
                    ids.add(int(value["response"]))
                file = value.get("file")
                if isinstance(file, dict) and file.get("id"):
                    ids.add(file["id"])
                for item in value.values():
                    collect(item)
            elif isinstance(value, list):
                for item in value:
                    collect(item)

        collect(response.json())
        return ids

    # --- flux complet ------------------------------------------------------------

    def test_full_flow_documents_are_downloadable_with_token(self):
        photo = self._upload_form_photo()
        photo_id = photo["document_id"]
        self.assertEqual(photo["url"], f"/got/orders/view-document/{photo_id}/")

        # Abans de crear l'informe (previsualització de la foto pujada)
        response = self._view(photo_id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"foto-formulari")

        report = self._add_report(photo_id)
        self.assertEqual(Document.objects.get(id=photo_id).entity, "ORDER_FORM_SUBMISSION")

        attachment = self._add_report_document(report)
        # Els adjunts es pugen amb el token de l'ordre com a entitat
        self.assertEqual(Document.objects.get(id=attachment["file"]["id"]).entity, self.order.token)

        shown = self._documents_shown_in_reports()
        self.assertEqual(shown, {photo_id, attachment["file"]["id"]})
        for document_id in shown:
            response = self._view(document_id)
            self.assertEqual(response.status_code, 200, f"document {document_id}")
            self.assertTrue(response.content)
            self.assertEqual(self._view(document_id, token="").status_code, 401)

    def test_gmao_report_documents_are_downloadable(self):
        report = OrderReport.objects.create(order=self.order, operator=self.operator, token="R-GMAO")
        report_photo = self._file_document("ORDER_REPORT", "gmao.jpg")
        OrderReportDocument.objects.create(order_report=report, file=report_photo, token="RD-GMAO")
        pending_photo = self._file_document("ORDER_FORM_SUBMISSION_PENDING", "pendent.jpg")

        self.assertEqual(self._view(report_photo.id).status_code, 200)
        self.assertEqual(self._view(pending_photo.id).status_code, 200)

    def test_backoffice_report_attachment_is_downloadable(self):
        """Adjunt pujat des del backoffice (order_report_document_view): entitat = token de l'ordre."""
        report = OrderReport.objects.create(order=self.order, operator=self.operator, token="R-BO")
        attachment = self._file_document(self.order.token, "backoffice.pdf")
        OrderReportDocument.objects.create(order_report=report, file=attachment, token="RD-BO")

        self.assertEqual(self._view(attachment.id).status_code, 200)

        # El backoffice ho descarrega pel documentmanager amb el token DRF
        client = APIClient()
        client.force_authenticate(User.objects.create_superuser("bo", "bo@example.com", "pwd"))
        response = client.get(f"/documentmanager/view-document/{attachment.id}/")
        self.assertEqual(response.status_code, 200)

    # --- accessos denegats -------------------------------------------------------

    def test_anonymous_request_is_rejected(self):
        photo_id = self._upload_form_photo()["document_id"]
        self.assertEqual(self._view(photo_id, token="").status_code, 401)
        self.assertEqual(self._view(photo_id, token="token-inventat").status_code, 401)

    def test_expired_token_is_rejected(self):
        photo_id = self._upload_form_photo()["document_id"]
        Token.objects.filter(token=self.token).update(expiration_date=timezone.now() - timedelta(days=1))
        self.assertEqual(self._view(photo_id).status_code, 401)

    def test_inactive_operator_is_rejected(self):
        photo_id = self._upload_form_photo()["document_id"]
        ReadingOperator.objects.filter(id=self.reading_operator.id).update(is_active=False)
        self.assertEqual(self._view(photo_id).status_code, 401)

    def test_reading_operator_without_order_operator_is_rejected(self):
        photo_id = self._upload_form_photo()["document_id"]
        ReadingOperator.objects.create(name="Lector", surname="Test", username="lector", password="pwd-lector")
        response = self.client.post(
            "/got/auth/login/",
            json.dumps({"username": "lector", "password": "pwd-lector"}),
            content_type="application/json",
        )
        self.assertEqual(self._view(photo_id, token=response.json()["token"]).status_code, 403)

    def test_documents_outside_orders_are_not_served(self):
        for entity in ("FACTURES", "CONTRACT", "FRAUD", "SEPA", "COMUNICACIO", "ORDRES"):
            document = self._file_document(entity, f"{entity}.pdf")
            self.assertEqual(self._view(document.id).status_code, 404, entity)

    def test_inactive_document_is_not_served(self):
        document = self._file_document("ORDER", "inactiu.jpg", is_active=False)
        self.assertEqual(self._view(document.id).status_code, 404)

    def test_unknown_document_is_not_served(self):
        self.assertEqual(self._view(999999).status_code, 404)
