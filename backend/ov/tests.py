import csv
import os
import shutil
import tempfile
from datetime import date
from io import StringIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from billing.models import (
    GeneralPayment,
    GeneralPaymentSepaDocument,
    Invoice,
    InvoiceStatus,
    Reading,
)
from coredata.models import ConfigProject, Person, PersonBank
from contract.models import Contract, ContractStatus, PaymentType
from documentmanager.models import Document
from service.models import Meter, SupplyPoint

SLASH_TOKEN = "12345678/001"
PLAIN_TOKEN = "12345678"
HOLDER_TOKEN = "12345678Z"
PAYER_DNI = "87654321Y"
NIC = "12345/1234"


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


class ContractDetailRoleFlagsTests(TestCase):
    """Phase 2: `status` objectiu i banderes `is_holder` / `is_payer` als tres
    endpoints de detall de contracte, sense alterar `status_token`,
    `status_name` ni `is_account_holder`."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="ov-contract-detail-flags-test", password="not-used"
        )
        for token, value in (
            ("contract_termination_completed_token", "3"),
            ("contract_terminated_status", "-1"),
        ):
            if not ConfigProject.objects.filter(token=token).exists():
                ConfigProject.objects.create(token=token, value=value)

        cls.status = ContractStatus.objects.create(token="1", name="Activo")
        cls.holder = Person.objects.create(
            token=HOLDER_TOKEN, name="Test", surname="Holder"
        )
        cls.payer = Person.objects.create(
            token=PAYER_DNI, name="Test", surname="Payer"
        )
        cls.person_bank = PersonBank.objects.create(
            person=cls.payer, dni=PAYER_DNI, iban="ES12345678901234567890"
        )
        cls.payment_type = PaymentType.objects.create(token="DIRECT_DEBIT")
        cls.payment = GeneralPayment.objects.create(
            type=cls.payment_type, IBAN=cls.person_bank
        )
        cls.supply_point = SupplyPoint.objects.create(token=NIC)
        cls.contract = Contract.objects.create(
            token=PLAIN_TOKEN,
            status=cls.status,
            holder=cls.holder,
            payment=cls.payment,
            supply_point_default=cls.supply_point,
        )
        cls.no_status_contract = Contract.objects.create(
            token="87654321", holder=cls.holder, payment=cls.payment
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _contract_detail(self, token, **params):
        return self.client.get(reverse("contract-ov"), {"contract_token": token, **params})

    def test_status_object_is_added_alongside_legacy_fields(self):
        response = self._contract_detail(PLAIN_TOKEN)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status_token"], "1")
        self.assertEqual(response.data["status_name"], "Activo")
        self.assertEqual(response.data["status"], {"token": "1", "name": "Activo"})

    def test_status_object_is_null_without_status(self):
        response = self._contract_detail(self.no_status_contract.token)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["status"])

    def test_role_flags_are_absent_without_dni(self):
        response = self._contract_detail(PLAIN_TOKEN)

        self.assertEqual(response.status_code, 200)
        for key in ("is_account_holder", "is_holder", "is_payer"):
            self.assertNotIn(key, response.data)

    def test_is_holder_true_when_dni_matches_contract_holder(self):
        # El `dni` es normalitza (espais i minúscules).
        response = self._contract_detail(PLAIN_TOKEN, dni=f"  {HOLDER_TOKEN.lower()} ")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_holder"])
        self.assertFalse(response.data["is_account_holder"])
        self.assertFalse(response.data["is_payer"])

    def test_is_payer_true_when_dni_matches_direct_debit_account_holder(self):
        response = self._contract_detail(PLAIN_TOKEN, dni=PAYER_DNI)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_payer"])
        self.assertTrue(response.data["is_account_holder"])
        self.assertFalse(response.data["is_holder"])

    def test_flags_are_present_on_contract_by_token_endpoint(self):
        response = self.client.get(
            reverse("contract-detail-by-token-ov", kwargs={"token": PLAIN_TOKEN}),
            {"dni": HOLDER_TOKEN},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], {"token": "1", "name": "Activo"})
        self.assertTrue(response.data["is_holder"])
        self.assertFalse(response.data["is_payer"])

    def test_flags_are_present_on_contract_by_nic_endpoint(self):
        response = self.client.get(
            reverse("contract-by-nic-ov", kwargs={"nic": NIC}),
            {"dni": PAYER_DNI},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], {"token": "1", "name": "Activo"})
        self.assertTrue(response.data["is_payer"])
        self.assertFalse(response.data["is_holder"])


class InvoiceStatusObjectTests(TestCase):
    """Phase 2: objecte `status` als endpoints de factures, sense alterar
    `invoice_status`."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="ov-invoice-status-test", password="not-used"
        )
        for token, value in (
            ("contract_termination_completed_token", "3"),
            ("contract_terminated_status", "-1"),
            ("invoice_status_paid_token", "0"),
            ("invoice_status_cancelled_token", "-1"),
        ):
            if not ConfigProject.objects.filter(token=token).exists():
                ConfigProject.objects.create(token=token, value=value)

        cls.holder = Person.objects.create(
            token=HOLDER_TOKEN, name="Test", surname="Holder"
        )
        cls.contract = Contract.objects.create(token=PLAIN_TOKEN, holder=cls.holder)

        cls.status = InvoiceStatus.objects.create(token="3", name="Enviada")
        cls.preinvoice_status = InvoiceStatus.objects.create(
            token="1", name="Prefactura"
        )

        cls.invoice = Invoice.objects.create(
            token="INV-001",
            contract=cls.contract,
            status=cls.status,
            issue_date=date(2026, 1, 15),
        )
        cls.invoice_without_status = Invoice.objects.create(
            token="INV-002",
            contract=cls.contract,
            status=None,
            issue_date=date(2026, 1, 16),
        )
        cls.preinvoice = Invoice.objects.create(
            token="INV-003",
            contract=cls.contract,
            status=cls.preinvoice_status,
            issue_date=date(2026, 1, 17),
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _as_dict(self, data):
        return {item["invoice_token"]: item for item in data}

    def test_list_adds_status_object_alongside_invoice_status(self):
        response = self.client.get(
            reverse("invoices-ov"), {"contract_token": PLAIN_TOKEN}
        )

        self.assertEqual(response.status_code, 200)
        item = self._as_dict(response.data)["INV-001"]
        self.assertEqual(item["invoice_status"], "Enviada")
        self.assertEqual(item["status"], {"token": "3", "name": "Enviada"})

    def test_list_still_excludes_preinvoices(self):
        response = self.client.get(
            reverse("invoices-ov"), {"contract_token": PLAIN_TOKEN}
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("INV-003", self._as_dict(response.data))

    def test_list_status_is_null_without_status(self):
        response = self.client.get(
            reverse("invoices-ov"), {"contract_token": PLAIN_TOKEN}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self._as_dict(response.data)["INV-002"]["status"])

    def test_detail_adds_status_object(self):
        response = self.client.get(
            reverse("invoice-ov"),
            {"contract_token": PLAIN_TOKEN, "invoice_token": "INV-001"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["invoice_status"], "Enviada")
        self.assertEqual(response.data["status"], {"token": "3", "name": "Enviada"})

    def test_unpayed_invoices_add_status_object(self):
        response = self.client.get(
            reverse("unpayed-invoices-ov"),
            {"contract_token": PLAIN_TOKEN, "statuses": "3"},
        )

        self.assertEqual(response.status_code, 200)
        item = self._as_dict(response.data)["INV-001"]
        self.assertEqual(item["status"], {"token": "3", "name": "Enviada"})

    def test_full_detail_adds_status_object(self):
        response = self.client.get(
            reverse("invoice-detail-by-token-ov", kwargs={"token": "INV-001"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["invoice_status"], "Enviada")
        self.assertEqual(response.data["status"], {"token": "3", "name": "Enviada"})


class InvoiceFilterAlignmentTests(TestCase):
    """Phase 2: `/ov/unpayed-invoices/` comparteix els filtres base de
    `/ov/invoices/` (sense pre-factures) i `/ov/invoices/` retorna 404 si el
    contracte no existeix."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="ov-invoice-filters-test", password="not-used"
        )
        for token, value in (
            ("contract_termination_completed_token", "3"),
            ("contract_terminated_status", "-1"),
            ("invoice_status_paid_token", "0"),
            ("invoice_status_cancelled_token", "-1"),
        ):
            if not ConfigProject.objects.filter(token=token).exists():
                ConfigProject.objects.create(token=token, value=value)

        cls.holder = Person.objects.create(
            token=HOLDER_TOKEN, name="Test", surname="Holder"
        )
        cls.contract = Contract.objects.create(token=PLAIN_TOKEN, holder=cls.holder)

        cls.sent_status = InvoiceStatus.objects.create(token="3", name="Enviada")
        cls.confirmed_status = InvoiceStatus.objects.create(token="2", name="Confirmada")
        cls.preinvoice_status = InvoiceStatus.objects.create(
            token="1", name="Prefactura"
        )

        cls.sent_invoice = Invoice.objects.create(
            token="INV-001",
            contract=cls.contract,
            status=cls.sent_status,
            issue_date=date(2026, 1, 15),
        )
        cls.confirmed_invoice = Invoice.objects.create(
            token="INV-002",
            contract=cls.contract,
            status=cls.confirmed_status,
            issue_date=date(2026, 1, 16),
        )
        cls.preinvoice = Invoice.objects.create(
            token="INV-003",
            contract=cls.contract,
            status=cls.preinvoice_status,
            issue_date=date(2026, 1, 17),
        )
        cls.orphan_invoice = Invoice.objects.create(
            token="INV-ORPHAN",
            contract=None,
            status=cls.sent_status,
            issue_date=date(2026, 1, 18),
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _tokens(self, data):
        return {item["invoice_token"] for item in data}

    def test_unpayed_excludes_preinvoices_with_mixed_statuses(self):
        response = self.client.get(
            reverse("unpayed-invoices-ov"),
            {"contract_token": PLAIN_TOKEN, "statuses": "2,3,1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._tokens(response.data), {"INV-001", "INV-002"})

    def test_unpayed_preinvoice_only_returns_empty(self):
        response = self.client.get(
            reverse("unpayed-invoices-ov"),
            {"contract_token": PLAIN_TOKEN, "statuses": "1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_unpayed_keeps_statuses_filter(self):
        response = self.client.get(
            reverse("unpayed-invoices-ov"),
            {"contract_token": PLAIN_TOKEN, "statuses": "2"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._tokens(response.data), {"INV-002"})

    def test_unpayed_still_requires_statuses(self):
        response = self.client.get(
            reverse("unpayed-invoices-ov"), {"contract_token": PLAIN_TOKEN}
        )

        self.assertEqual(response.status_code, 400)

    def test_list_unknown_contract_returns_404(self):
        response = self.client.get(
            reverse("invoices-ov"), {"contract_token": "NO-SUCH-TOKEN"}
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Contract not found"})

    def test_unpayed_unknown_contract_returns_404(self):
        response = self.client.get(
            reverse("unpayed-invoices-ov"),
            {"contract_token": "NO-SUCH-TOKEN", "statuses": "3"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Contract not found"})


class ConsumptionBilledFilterTests(TestCase):
    """Phase 2: els endpoints de consums només retornen consums facturats
    (lectures vinculades a almenys una factura)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="ov-consumption-billed-test", password="not-used"
        )
        for token, value in (
            ("contract_termination_completed_token", "3"),
            ("contract_terminated_status", "-1"),
            ("invoice_status_paid_token", "0"),
            ("invoice_status_cancelled_token", "-1"),
        ):
            if not ConfigProject.objects.filter(token=token).exists():
                ConfigProject.objects.create(token=token, value=value)

        cls.status = ContractStatus.objects.create(token="1", name="Activo")
        cls.holder = Person.objects.create(
            token=HOLDER_TOKEN, name="Test", surname="Holder"
        )
        cls.meter = Meter.objects.create(code="MTR-TEST")
        cls.supply_point = SupplyPoint.objects.create(token=NIC, meter=cls.meter)
        cls.contract = Contract.objects.create(
            token=PLAIN_TOKEN,
            status=cls.status,
            holder=cls.holder,
            supply_point_default=cls.supply_point,
        )

        cls.billed_reading = Reading.objects.create(
            meter=cls.meter,
            contract=cls.contract,
            reading_date=date(2026, 1, 10),
            reading_value=1250.5,
            real_consumption=12.0,
        )
        cls.unbilled_reading = Reading.objects.create(
            meter=cls.meter,
            contract=cls.contract,
            reading_date=date(2026, 2, 10),
            reading_value=1300.0,
            real_consumption=15.0,
        )

        cls.sent_status = InvoiceStatus.objects.create(token="3", name="Enviada")
        cls.preinvoice_status = InvoiceStatus.objects.create(
            token="1", name="Prefactura"
        )
        cls.invoice = Invoice.objects.create(
            token="INV-001",
            contract=cls.contract,
            status=cls.sent_status,
            issue_date=date(2026, 1, 15),
            billing_period_year=2026,
            billing_period_month=1,
        )
        cls.invoice.readings.add(cls.billed_reading)
        cls.preinvoice = Invoice.objects.create(
            token="INV-002",
            contract=cls.contract,
            status=cls.preinvoice_status,
            issue_date=date(2026, 1, 20),
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _list(self, **params):
        return self.client.get(
            reverse("consumptions-ov"), {"contract_token": PLAIN_TOKEN, **params}
        )

    def _csv_ids(self, response):
        content = b"".join(response.streaming_content).decode("utf-8")
        return {row["id"] for row in csv.DictReader(StringIO(content))}

    def test_list_excludes_unbilled_readings(self):
        response = self._list()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            [item["id"] for item in response.data["results"]],
            [self.billed_reading.id],
        )

    def test_list_period_comes_from_linked_invoice(self):
        response = self._list()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["period"], "2026-1T")

    def test_list_date_filter_keeps_billed_only(self):
        response = self._list(date_from="2026-01-01", date_to="2026-12-31")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            [item["id"] for item in response.data["results"]],
            [self.billed_reading.id],
        )

    def test_single_download_billed_reading_returns_csv(self):
        response = self.client.get(
            reverse("consumption-download-ov", kwargs={"id": self.billed_reading.id}),
            {"contract_token": PLAIN_TOKEN, "format": "csv"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._csv_ids(response), {str(self.billed_reading.id)})

    def test_single_download_unbilled_reading_returns_404(self):
        response = self.client.get(
            reverse(
                "consumption-download-ov", kwargs={"id": self.unbilled_reading.id}
            ),
            {"contract_token": PLAIN_TOKEN, "format": "csv"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Reading not found"})

    def test_bulk_download_date_range_excludes_unbilled(self):
        response = self.client.post(
            reverse("consumptions-download-ov"),
            {"contract_token": PLAIN_TOKEN, "format": "csv"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._csv_ids(response), {str(self.billed_reading.id)})

    def test_bulk_download_reading_ids_silently_excludes_unbilled(self):
        response = self.client.post(
            reverse("consumptions-download-ov"),
            {
                "contract_token": PLAIN_TOKEN,
                "format": "csv",
                "reading_ids": [self.billed_reading.id, self.unbilled_reading.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._csv_ids(response), {str(self.billed_reading.id)})

    def test_bulk_download_unknown_reading_id_still_returns_400(self):
        response = self.client.post(
            reverse("consumptions-download-ov"),
            {
                "contract_token": PLAIN_TOKEN,
                "format": "csv",
                "reading_ids": [999999],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_billed_consumptions_still_includes_preinvoices(self):
        response = self.client.get(
            reverse("billed-consumptions-ov"), {"contract_token": PLAIN_TOKEN}
        )

        self.assertEqual(response.status_code, 200)
        timestamps = {item["timestamp"] for item in response.data}
        self.assertEqual(timestamps, {"2026-01-15", "2026-01-20"})


class SepaDocumentUploadTests(TestCase):
    """Phase 2: `upload-sepa-signed` desa el mandat al gestor documental i el
    vincula a la forma de pagament del contracte."""

    @classmethod
    def setUpClass(cls):
        cls._storage_dir = tempfile.mkdtemp()
        cls._storage_override = override_settings(
            DOCUMENT_STORAGE_PATH=cls._storage_dir
        )
        cls._storage_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._storage_override.disable()
        shutil.rmtree(cls._storage_dir, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="ov-sepa-upload-test", password="not-used"
        )
        for token, value in (
            ("contract_termination_completed_token", "3"),
            ("contract_terminated_status", "-1"),
        ):
            if not ConfigProject.objects.filter(token=token).exists():
                ConfigProject.objects.create(token=token, value=value)

        cls.status = ContractStatus.objects.create(token="1", name="Activo")
        cls.holder = Person.objects.create(
            token=HOLDER_TOKEN, name="Test", surname="Holder"
        )
        cls.person_bank = PersonBank.objects.create(
            person=cls.holder, dni=HOLDER_TOKEN, iban="ES12345678901234567890"
        )
        cls.payment_type = PaymentType.objects.create(token="DIRECT_DEBIT")
        cls.payment = GeneralPayment.objects.create(
            token="GP-001", type=cls.payment_type, IBAN=cls.person_bank
        )
        cls.contract = Contract.objects.create(
            token=PLAIN_TOKEN,
            status=cls.status,
            holder=cls.holder,
            payment=cls.payment,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _upload(
        self,
        filename="sepa_mandate.pdf",
        content=b"%PDF-1.4 test mandate",
        iban="ES12345678901234567890",
        contract_token=PLAIN_TOKEN,
    ):
        return self.client.post(
            reverse(
                "upload-sepa-signed-ov", kwargs={"contract_token": contract_token}
            ),
            {
                "sepa": SimpleUploadedFile(
                    filename, content, content_type="application/pdf"
                ),
                "iban": iban,
            },
            format="multipart",
        )

    def test_upload_returns_201_with_unchanged_body(self):
        response = self._upload()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data, {"contract_token": PLAIN_TOKEN, "success": True}
        )

    def test_upload_archives_document_and_links_it_to_payment(self):
        response = self._upload()

        self.assertEqual(response.status_code, 201)
        document = Document.objects.get(
            entity="SEPA", field="CONTRACT", entity_id=self.payment.id
        )
        self.assertEqual(document.service, "hdd")
        self.assertEqual(document.document_name, "sepa_mandate.pdf")
        self.assertTrue(os.path.exists(document.location))
        with open(document.location, "rb") as stored:
            self.assertEqual(stored.read(), b"%PDF-1.4 test mandate")

        linked = GeneralPaymentSepaDocument.objects.get(
            general_payment=self.payment
        )
        self.assertEqual(linked.file_id, document.id)
        self.assertTrue(linked.checked)

    def test_reupload_replaces_mandate_and_versions_document(self):
        self._upload(content=b"first")
        response = self._upload(content=b"second")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            GeneralPaymentSepaDocument.objects.filter(
                general_payment=self.payment
            ).count(),
            1,
        )
        documents = Document.objects.filter(
            entity="SEPA", field="CONTRACT", entity_id=self.payment.id
        ).order_by("version")
        self.assertEqual(
            list(documents.values_list("version", flat=True)), [1, 2]
        )
        linked = GeneralPaymentSepaDocument.objects.get(
            general_payment=self.payment
        )
        self.assertEqual(linked.file_id, documents.last().id)
        self.assertEqual(linked.file.parent_document_id, documents.first().id)
        self.assertTrue(linked.checked)

    def test_reupload_with_different_filename_replaces_link(self):
        self._upload(filename="first.pdf")
        response = self._upload(filename="second.pdf")

        self.assertEqual(response.status_code, 201)
        linked = GeneralPaymentSepaDocument.objects.get(
            general_payment=self.payment
        )
        self.assertEqual(linked.file.document_name, "second.pdf")

    def test_iban_mismatch_returns_400_without_storing_document(self):
        before = Document.objects.count()

        response = self._upload(iban="ES00000000000000000000")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Document.objects.count(), before)
        self.assertFalse(
            GeneralPaymentSepaDocument.objects.filter(
                general_payment=self.payment
            ).exists()
        )

    def test_unknown_contract_returns_404(self):
        response = self._upload(contract_token="NO-SUCH-TOKEN")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Contract not found"})

    def test_invalid_extension_returns_400(self):
        response = self._upload(filename="mandate.exe")

        self.assertEqual(response.status_code, 400)
        self.assertIn("sepa", response.data)

    def test_missing_fields_returns_400(self):
        response = self.client.post(
            reverse(
                "upload-sepa-signed-ov", kwargs={"contract_token": PLAIN_TOKEN}
            ),
            {},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("sepa", response.data)
        self.assertIn("iban", response.data)

    def test_billing_data_reports_sepa_document_state(self):
        url = reverse("billing-data-ov")

        before = self.client.get(url, {"contract_token": PLAIN_TOKEN})
        self.assertEqual(before.status_code, 200)
        self.assertIs(before.data["has_sepa_document"], False)

        self._upload()

        after = self.client.get(url, {"contract_token": PLAIN_TOKEN})
        self.assertEqual(after.status_code, 200)
        self.assertIs(after.data["has_sepa_document"], True)

    def test_billing_data_reports_false_without_payment(self):
        contract = Contract.objects.create(token="87654321", holder=self.holder)

        response = self.client.get(
            reverse("billing-data-ov"), {"contract_token": contract.token}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIs(response.data["has_sepa_document"], False)

    def test_contact_data_reports_sepa_document_state(self):
        url = reverse("contact-data-ov")

        before = self.client.get(url, {"contract_token": PLAIN_TOKEN})
        self.assertEqual(before.status_code, 200)
        self.assertIs(before.data["has_sepa_document"], False)

        self._upload()

        after = self.client.get(url, {"contract_token": PLAIN_TOKEN})
        self.assertEqual(after.status_code, 200)
        self.assertIs(after.data["has_sepa_document"], True)

    def test_contract_detail_reports_sepa_document_state(self):
        url = reverse(
            "contract-detail-by-token-ov", kwargs={"token": PLAIN_TOKEN}
        )

        before = self.client.get(url)
        self.assertEqual(before.status_code, 200)
        self.assertIs(before.data["has_sepa_document"], False)

        self._upload()

        after = self.client.get(url)
        self.assertEqual(after.status_code, 200)
        self.assertIs(after.data["has_sepa_document"], True)

    def test_download_sepa_signed_returns_404_before_upload(self):
        response = self.client.get(
            reverse("sepa-signed-ov", kwargs={"contract_token": PLAIN_TOKEN})
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "SEPA document not found"})

    def test_download_sepa_signed_returns_archived_file(self):
        self._upload(content=b"%PDF-1.4 archived mandate")

        response = self.client.get(
            reverse("sepa-signed-ov", kwargs={"contract_token": PLAIN_TOKEN})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"%PDF-1.4 archived mandate")
        self.assertIn("sepa_mandate.pdf", response["Content-Disposition"])

    def test_download_sepa_signed_unknown_contract_returns_404(self):
        response = self.client.get(
            reverse("sepa-signed-ov", kwargs={"contract_token": "NO-SUCH-TOKEN"})
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Contract not found"})

    def test_download_sepa_signed_without_file_returns_404(self):
        GeneralPaymentSepaDocument.objects.create(
            general_payment=self.payment, file=None
        )

        response = self.client.get(
            reverse("sepa-signed-ov", kwargs={"contract_token": PLAIN_TOKEN})
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "SEPA document not found"})
