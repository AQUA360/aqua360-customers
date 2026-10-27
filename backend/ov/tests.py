import base64
import csv
import os
import shutil
import tempfile
import zipfile
from datetime import date
from decimal import Decimal
from io import BytesIO, StringIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import resolve, reverse
from django.utils import translation
from rest_framework.test import APIClient

from billing.models import (
    GeneralPayment,
    GeneralPaymentSepaDocument,
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentMovement,
    PaymentRemittanceReturn,
    PaymentStatus,
    Reading,
)
from coredata.models import (
    Address,
    City,
    ConfigProject,
    Country,
    Person,
    PersonAddress,
    PersonBank,
    PersonContact,
    PostalCode,
    Street,
    StreetNumber,
    StreetType,
)
from contract.models import (
    ContractDataChange,
    Contract,
    ContractPriceRate,
    ContractRequest,
    ContractRequestStatus,
    ContractRequestType,
    ContractStatus,
    PaymentType,
)
from documentmanager.models import Document
from logger.models import LogContractRequestStatus, LogIncidentStatusChange
from notification.models import Incident, IncidentStatus, IncidentType
from order.models import OrderType
from pricing.models import (
    BillingRange,
    LineItemType,
    PriceInterval,
    PriceIntervalStretch,
    PriceRate,
    PriceVariableInterval,
    PriceVariableIntervalStretch,
)
from service.models import Company, Exploitation, Meter, Property, SupplyPoint
from ov.throttles import (
    ContractProcedureThrottle,
    PaymentReceiptThrottle,
    PersonDataThrottle,
    QuickPayThrottle,
    ReturnRequestThrottle,
)
from ov.views import (
    ContractProcedureOVView,
    InvoiceReturnRequestOVView,
    PaymentReceiptOVView,
    PersonDataOVView,
    QuickPayOVView,
)

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

    def test_contract_list_adds_status_object(self):
        response = self.client.get(
            reverse("contracts-ov"),
            {"dni": HOLDER_TOKEN},
        )

        self.assertEqual(response.status_code, 200)
        item = next(
            result
            for result in response.data["results"]
            if result["token"] == PLAIN_TOKEN
        )
        self.assertEqual(item["status"], {"token": "1", "name": "Activo"})
        self.assertIn("is_account_holder", item)

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
            ("invoice_status_cancelled_token", "-6"),
            ("invoice_status_confirmed_token", "2"),
            ("invoice_status_sent_token", "3"),
            ("invoice_status_expired_token", "-1"),
            ("invoice_status_endowment_token", "-3"),
            ("invoice_status_commitment_token", "4"),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={"value": value})

        cls.holder = Person.objects.create(
            token=HOLDER_TOKEN, name="Test", surname="Holder"
        )
        cls.contract = Contract.objects.create(token=PLAIN_TOKEN, holder=cls.holder)

        cls.sent_status = InvoiceStatus.objects.create(token="3", name="Enviada")
        cls.confirmed_status = InvoiceStatus.objects.create(token="2", name="Confirmada")
        cls.preinvoice_status = InvoiceStatus.objects.create(
            token="1", name="Prefactura"
        )
        cls.endowment_status = InvoiceStatus.objects.create(
            token="-3", name="Morosidad"
        )
        cls.commitment_status = InvoiceStatus.objects.create(
            token="4", name="En compromiso"
        )

        cls.sent_invoice = Invoice.objects.create(
            token="INV-001",
            contract=cls.contract,
            status=cls.sent_status,
            issue_date=date(2026, 1, 15),
            left_to_pay=Decimal("25.00"),
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
        cls.endowment_invoice = Invoice.objects.create(
            token="INV-004",
            contract=cls.contract,
            status=cls.endowment_status,
            issue_date=date(2026, 1, 18),
        )
        cls.commitment_invoice = Invoice.objects.create(
            token="INV-005",
            contract=cls.contract,
            status=cls.commitment_status,
            issue_date=date(2026, 1, 19),
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

    def test_unpaid_mode_uses_configured_unpaid_states(self):
        response = self.client.get(
            reverse("unpayed-invoices-ov"),
            {"contract_token": PLAIN_TOKEN, "unpaid": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self._tokens(response.data),
            {"INV-001", "INV-002", "INV-004", "INV-005"},
        )

    def test_explicit_statuses_take_precedence_over_unpaid_mode(self):
        response = self.client.get(
            reverse("unpayed-invoices-ov"),
            {
                "contract_token": PLAIN_TOKEN,
                "statuses": "2",
                "unpaid": "true",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._tokens(response.data), {"INV-002"})

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

    def test_upload_locks_payment_before_calculating_document_version(self):
        from documentmanager.utils.main_utils import upload_document

        outer_savepoints = list(connection.savepoint_ids)
        with CaptureQueriesContext(connection) as queries:
            def upload_with_lock(*args, **kwargs):
                self.assertEqual(len(connection.savepoint_ids), len(outer_savepoints) + 1)
                self.assertTrue(any(
                    '"billing_generalpayment"' in query["sql"]
                    and "FOR UPDATE" in query["sql"]
                    for query in queries.captured_queries
                ))
                return upload_document(*args, **kwargs)

            with patch("ov.views.upload_document", side_effect=upload_with_lock):
                response = self._upload()

        self.assertEqual(response.status_code, 201)

    def test_upload_rejects_iban_changed_before_payment_lock(self):
        new_bank = PersonBank.objects.create(
            person=self.holder, iban="ES00000000000000000000", name="New holder"
        )
        select_for_update = GeneralPayment.objects.select_for_update

        def change_before_lock():
            GeneralPayment.objects.filter(pk=self.payment.pk).update(IBAN=new_bank)
            return select_for_update()

        with patch(
            "ov.views.GeneralPayment.objects.select_for_update", side_effect=change_before_lock
        ), patch("ov.views.upload_document") as upload:
            response = self._upload()

        self.assertEqual(response.status_code, 400)
        upload.assert_not_called()
        self.assertFalse(Document.objects.filter(entity="SEPA").exists())

    def test_upload_uses_iban_and_folder_from_locked_payment(self):
        from documentmanager.utils.main_utils import upload_document

        new_bank = PersonBank.objects.create(
            person=self.holder, iban="ES00000000000000000000", name="New holder"
        )
        select_for_update = GeneralPayment.objects.select_for_update

        def change_before_lock():
            GeneralPayment.objects.filter(pk=self.payment.pk).update(IBAN=new_bank)
            return select_for_update()

        with patch(
            "ov.views.GeneralPayment.objects.select_for_update", side_effect=change_before_lock
        ), patch("ov.views.upload_document", wraps=upload_document) as upload:
            response = self._upload(iban=new_bank.iban)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(upload.call_args.args[5], "NEW_HOLDER")

    def test_update_iban_locks_and_modifies_reloaded_payment(self):
        from ov.serializers import UpdateBillingDataOVIBANSerializer

        contract = Contract.objects.select_related("payment__IBAN").get(pk=self.contract.pk)
        current_bank = PersonBank.objects.create(
            person=self.holder, iban="ES00000000000000000000", name="Current holder"
        )
        GeneralPayment.objects.filter(pk=self.payment.pk).update(
            IBAN=current_bank, dir3="concurrent change"
        )
        serializer = UpdateBillingDataOVIBANSerializer(data={
            "iban": "es11111111111111111111", "nif": self.holder.token,
            "iban_holder_name": "New holder", "iban_holder_dni": self.holder.token,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        outer_savepoints = list(connection.savepoint_ids)
        save = PersonBank.save

        with CaptureQueriesContext(connection) as queries:
            def save_with_payment_lock(bank, *args, **kwargs):
                self.assertEqual(len(connection.savepoint_ids), len(outer_savepoints) + 1)
                self.assertTrue(any(
                    '"billing_generalpayment"' in query["sql"] and "FOR UPDATE" in query["sql"]
                    for query in queries.captured_queries
                ))
                return save(bank, *args, **kwargs)

            with patch.object(PersonBank, "save", save_with_payment_lock):
                updated = serializer.update(contract, serializer.validated_data)

        self.payment.refresh_from_db()
        current_bank.refresh_from_db()
        self.person_bank.refresh_from_db()
        self.assertEqual(self.payment.IBAN.iban, "ES11111111111111111111")
        self.assertEqual(updated.payment.IBAN_id, self.payment.IBAN_id)
        self.assertEqual(self.payment.dir3, "concurrent change")
        self.assertFalse(current_bank.is_active)
        self.assertFalse(current_bank.is_default)
        self.assertIsNotNone(current_bank.deactivated_at)
        self.assertTrue(self.person_bank.is_active)
        change = ContractDataChange.objects.get(contract=self.contract)
        self.assertEqual(change.previous_payment_id, current_bank.pk)
        self.assertEqual(change.new_payment_id, self.payment.IBAN_id)

    def test_failed_link_replacement_rolls_back_new_document_and_keeps_old_link(self):
        self.assertEqual(self._upload(content=b"original").status_code, 201)
        original = GeneralPaymentSepaDocument.objects.get(general_payment=self.payment)
        document_ids = list(Document.objects.values_list("pk", flat=True))

        with patch(
            "ov.views.GeneralPaymentSepaDocument.objects.create",
            side_effect=RuntimeError("link replacement failed"),
        ), self.assertRaisesMessage(RuntimeError, "link replacement failed"):
            self._upload(content=b"replacement")

        self.assertEqual(list(Document.objects.values_list("pk", flat=True)), document_ids)
        self.assertEqual(
            GeneralPaymentSepaDocument.objects.get(general_payment=self.payment).pk,
            original.pk,
        )

    def test_reupload_with_different_filename_replaces_link(self):
        self._upload(filename="first.pdf")
        response = self._upload(filename="second.pdf")

        self.assertEqual(response.status_code, 201)
        linked = GeneralPaymentSepaDocument.objects.get(
            general_payment=self.payment
        )
        self.assertEqual(linked.file.document_name, "second.pdf")

    def test_reupload_keeps_version_chain_for_existing_document(self):
        from documentmanager.utils.main_utils import upload_document

        legacy = upload_document(
            SimpleUploadedFile("sepa_mandate.pdf", b"legacy mandate"),
            "SEPA", "CONTRACT", self.payment.id, self.payment.token,
            "SEPA", "hdd", "sepa_mandate.pdf",
        )
        GeneralPaymentSepaDocument.objects.create(
            general_payment=self.payment, file=legacy, checked=True
        )

        response = self._upload(content=b"replacement mandate")

        self.assertEqual(response.status_code, 201)
        document = GeneralPaymentSepaDocument.objects.get(
            general_payment=self.payment
        ).file
        self.assertEqual(document.version, 2)
        self.assertEqual(document.parent_document_id, legacy.pk)
        self.assertEqual(document.document_name, "sepa_mandate(2).pdf")
        self.assertEqual(
            os.path.dirname(document.location),
            os.path.join(os.path.dirname(legacy.location), str(self.payment.id)),
        )
        with open(legacy.location, "rb") as stored:
            self.assertEqual(stored.read(), b"legacy mandate")

    def test_same_filename_for_different_payments_preserves_each_version(self):
        other_payment = GeneralPayment.objects.create(
            token="GP-002", type=self.payment_type, IBAN=self.person_bank
        )
        other_contract = Contract.objects.create(
            token="OTHER-SEPA-CONTRACT", holder=self.holder, payment=other_payment
        )
        self.assertEqual(self._upload(content=b"first").status_code, 201)
        self.assertEqual(self._upload(content=b"second").status_code, 201)
        self.assertEqual(
            self._upload(
                content=b"other", contract_token=other_contract.token
            ).status_code,
            201,
        )

        documents = Document.objects.filter(
            entity="SEPA", field="CONTRACT", entity_id=self.payment.id
        ).order_by("version")
        other_document = GeneralPaymentSepaDocument.objects.get(
            general_payment=other_payment
        ).file
        all_documents = [*documents, other_document]
        self.assertEqual(len({doc.location for doc in all_documents}), 3)
        for document, content in zip(all_documents, (b"first", b"second", b"other")):
            with open(document.location, "rb") as stored:
                self.assertEqual(stored.read(), content)
        self.assertEqual(other_document.version, 1)

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

    def test_download_sepa_signed_returns_404_when_storage_returns_none(self):
        self._upload()

        with patch("ov.views.download_document", return_value=None):
            response = self.client.get(
                reverse("sepa-signed-ov", kwargs={"contract_token": PLAIN_TOKEN})
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "SEPA document not found"})

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


class DictionaryEndpointsTests(TestCase):
    """Diccionaris `token`/`name` per al frontal OV: estats de contracte,
    formes de pagament, estats de factura i tarifes de tràmits actives."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="ov-dictionary-test", password="not-used"
        )
        cls.status_late = ContractStatus.objects.create(
            token="2", name="Inactivo", position=2
        )
        cls.status_first = ContractStatus.objects.create(
            token="1", name="Activo", position=1
        )
        cls.payment_late = PaymentType.objects.create(
            token="BANK_TRANSFER", name="Transferència", position=2
        )
        cls.payment_first = PaymentType.objects.create(
            token="DIRECT_DEBIT", name="Domiciliació", position=1, is_default=True
        )
        cls.invoice_status_late = InvoiceStatus.objects.create(
            token="-1", name="Vencida", position=2
        )
        cls.invoice_status_first = InvoiceStatus.objects.create(
            token="0", name="Pagada", position=1
        )
        cls.tariff_inactive = PriceRate.objects.create(
            token="TR-OFF", name="Tarifa Z", is_active=False
        )

        cls.tariff_variable = cls._tariff_with_range("TR-VAR", "Tarifa A")
        caliber_interval = PriceInterval.objects.create(
            token="PI-DM-MET", units="dm_met"
        )
        LineItemType.objects.create(
            billing_range=cls.tariff_variable.billing_range_active,
            token="LIT-VAR",
            name="Alta per calibre",
            price_interval=caliber_interval,
        )
        PriceIntervalStretch.objects.create(
            price_interval=caliber_interval,
            name_stretch="Calibre 13",
            stretch=1,
            end_stretch=13,
            price=45.0,
        )
        PriceIntervalStretch.objects.create(
            price_interval=caliber_interval,
            name_stretch="Calibre 20",
            stretch=14,
            end_stretch=20,
            price=78.5,
        )

        cls.tariff_fixed = cls._tariff_with_range("TR-FIXED", "Tarifa B")
        LineItemType.objects.create(
            billing_range=cls.tariff_fixed.billing_range_active,
            token="LIT-FIX",
            name="Fiança",
            price=100.0,
        )

        cls.tariff_mixed = cls._tariff_with_range("TR-MIXED", "Tarifa C")
        mixed_range = cls.tariff_mixed.billing_range_active
        LineItemType.objects.create(
            billing_range=mixed_range,
            token="LIT-MIX-FIX",
            name="Canon",
            price=3.5,
        )
        consumption_interval = PriceVariableInterval.objects.create(
            token="PVI-M3", units="m3"
        )
        LineItemType.objects.create(
            billing_range=mixed_range,
            token="LIT-MIX-VAR",
            name="Consum",
            price_variable=consumption_interval,
        )
        PriceVariableIntervalStretch.objects.create(
            price_variable_interval=consumption_interval,
            name_stretch="Bloc 1",
            stretch=1,
            end_stretch=10,
            price=0.5,
        )

    @classmethod
    def _tariff_with_range(cls, token, name):
        tariff = PriceRate.objects.create(token=token, name=name, is_active=True)
        billing_range = BillingRange.objects.create(
            price_rate=tariff, start=date(2026, 1, 1), is_active=True
        )
        tariff.billing_range_active = billing_range
        tariff.save(update_fields=["billing_range_active"])
        return tariff

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _tariffs_by_token(self):
        response = self.client.get(
            reverse("procedure-tariffs-dictionary-ov")
        )

        self.assertEqual(response.status_code, 200)
        return {item["token"]: item for item in response.data}

    def test_contract_statuses_returns_token_and_name_ordered_by_position(self):
        response = self.client.get(
            reverse("contract-statuses-dictionary-ov")
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            [
                {"token": "1", "name": "Activo"},
                {"token": "2", "name": "Inactivo"},
            ],
        )
        self.assertEqual(set(response.data[0]), {"token", "name"})

    def test_payment_types_returns_token_and_name_ordered_by_position(self):
        response = self.client.get(reverse("payment-types-dictionary-ov"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            [
                {"token": "DIRECT_DEBIT", "name": "Domiciliació"},
                {"token": "BANK_TRANSFER", "name": "Transferència"},
            ],
        )
        self.assertEqual(set(response.data[0]), {"token", "name"})

    def test_invoice_statuses_returns_token_and_name_ordered_by_position(self):
        response = self.client.get(
            reverse("invoice-statuses-dictionary-ov")
        )

        self.assertEqual(response.status_code, 200)
        by_token = {item["token"]: item for item in response.data}
        self.assertEqual(by_token["0"], {"token": "0", "name": "Pagada"})
        self.assertEqual(by_token["-1"], {"token": "-1", "name": "Vencida"})
        tokens = [item["token"] for item in response.data]
        self.assertLess(tokens.index("0"), tokens.index("-1"))
        self.assertEqual(set(response.data[0]), {"token", "name"})

    def test_procedure_tariffs_returns_active_tariffs_ordered_by_name(self):
        response = self.client.get(
            reverse("procedure-tariffs-dictionary-ov")
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["token"] for item in response.data],
            ["TR-VAR", "TR-FIXED", "TR-MIXED"],
        )
        self.assertEqual(
            set(response.data[0]),
            {"token", "name", "type_price", "price", "price_table", "components"},
        )
        self.assertNotIn("is_bail", response.data[0])
        self.assertNotIn("is_return_fee", response.data[0])

    def test_fixed_tariff_returns_price_and_no_price_table(self):
        fixed = self._tariffs_by_token()["TR-FIXED"]

        self.assertEqual(fixed["type_price"], "fixed")
        self.assertEqual(fixed["price"], 100.0)
        self.assertIsNone(fixed["price_table"])
        self.assertEqual(len(fixed["components"]), 1)
        self.assertEqual(fixed["components"][0]["token"], "LIT-FIX")
        self.assertEqual(fixed["components"][0]["type_price"], "fixed")
        self.assertEqual(fixed["components"][0]["price"], 100.0)
        self.assertIsNone(fixed["components"][0]["price_table"])

    def test_variable_tariff_returns_caliber_price_table(self):
        variable = self._tariffs_by_token()["TR-VAR"]

        self.assertEqual(variable["type_price"], "variable")
        self.assertIsNone(variable["price"])
        self.assertEqual(
            variable["price_table"],
            {
                "units": "dm_met",
                "stretches": [
                    {
                        "name": "Calibre 13",
                        "min": 1,
                        "max": 13,
                        "price": 45.0,
                        "proportional_price": None,
                    },
                    {
                        "name": "Calibre 20",
                        "min": 14,
                        "max": 20,
                        "price": 78.5,
                        "proportional_price": None,
                    },
                ],
            },
        )
        self.assertEqual(len(variable["components"]), 1)
        self.assertEqual(
            variable["components"][0]["price_table"]["units"], "dm_met"
        )

    def test_mixed_tariff_sums_fixed_components_and_keeps_breakdown(self):
        mixed = self._tariffs_by_token()["TR-MIXED"]

        self.assertEqual(mixed["type_price"], "variable")
        self.assertEqual(mixed["price"], 3.5)
        self.assertEqual(mixed["price_table"]["units"], "m3")
        self.assertEqual(len(mixed["components"]), 2)
        by_token = {item["token"]: item for item in mixed["components"]}
        self.assertEqual(by_token["LIT-MIX-FIX"]["type_price"], "fixed")
        self.assertEqual(by_token["LIT-MIX-FIX"]["price"], 3.5)
        self.assertEqual(by_token["LIT-MIX-VAR"]["type_price"], "variable")
        self.assertIsNone(by_token["LIT-MIX-VAR"]["price"])
        self.assertEqual(
            by_token["LIT-MIX-VAR"]["price_table"]["units"], "m3"
        )

    def test_inactive_tariff_excluded(self):
        self.assertNotIn("TR-OFF", self._tariffs_by_token())

    def test_dictionary_endpoints_require_authentication(self):
        anonymous = APIClient()

        for name in (
            "contract-statuses-dictionary-ov",
            "payment-types-dictionary-ov",
            "invoice-statuses-dictionary-ov",
            "procedure-tariffs-dictionary-ov",
        ):
            with self.subTest(endpoint=name):
                self.assertEqual(anonymous.get(reverse(name)).status_code, 401)


class PropertiesOVTests(TestCase):
    """`GET /ov/properties/?search=` — autocompletat d'adreces de propietats
    actives amb el resultat paginat i l'adreça ja formatada."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="ov-properties-test", password="not-used"
        )
        street_type = StreetType.objects.create(
            abbreviation="C", name="Carrer"
        )
        city = City.objects.create(token="CITY-08001", name="Barcelona")
        postal_code = PostalCode.objects.create(code="08001")
        cls.street_major = Street.objects.create(
            name="Major", type=street_type, city=city
        )
        number = StreetNumber.objects.create(street=cls.street_major, number=123)
        cls.property = Property.objects.create(
            token="PR-001",
            name="Edifici Major",
            address_street=cls.street_major,
            address_street_number=number,
            address_postal_code=postal_code,
            address_city=city,
            is_active=True,
        )
        cls.other = Property.objects.create(
            token="PR-002",
            name="Casal Petit",
            cadastral="CAD-999",
            address_street=Street.objects.create(name="Petit"),
            address_postal_code=postal_code,
            address_city=city,
            is_active=True,
        )
        cls.inactive = Property.objects.create(
            token="PR-OFF",
            name="Major inactiva",
            address_street=cls.street_major,
            address_postal_code=postal_code,
            address_city=city,
            is_active=False,
        )
        street_type_cr = StreetType.objects.create(
            abbreviation="CR", name=""
        )
        street_cr = Street.objects.create(
            name="Sant Miquel", type=street_type_cr, city=city
        )
        cls.cr_property = Property.objects.create(
            token="PR-CR",
            name="CR/SANT MIQUEL, 33",
            address_street=street_cr,
            address_street_number=StreetNumber.objects.create(
                street=street_cr, number=33
            ),
            address_postal_code=postal_code,
            address_city=city,
            is_active=True,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _search(self, term, **params):
        return self.client.get(
            reverse("properties-ov"), {"search": term, **params}
        )

    def test_search_by_street_name_returns_formatted_address(self):
        response = self._search("Major")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["results"],
            [
                {
                    "token": "PR-001",
                    "address": "C. Major, 123, 08001 Barcelona",
                }
            ],
        )

    def test_search_by_number_matches_exact_value(self):
        response = self._search("123")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["token"] for item in response.data["results"]], ["PR-001"]
        )

    def test_search_by_postal_code_returns_matching_properties(self):
        response = self._search("08001")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["token"] for item in response.data["results"]],
            ["PR-001", "PR-002", "PR-CR"],
        )

    def test_search_ignores_trailing_dot_in_street_type(self):
        response = self._search("CR.")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["results"],
            [
                {
                    "token": "PR-CR",
                    "address": "CR. Sant Miquel, 33, 08001 Barcelona",
                }
            ],
        )

    def test_multi_term_search_matches_across_columns(self):
        response = self._search("CR. Sant 33")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["token"] for item in response.data["results"]], ["PR-CR"]
        )

    def test_punctuation_only_search_returns_400(self):
        response = self._search("...")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {"error": "Search must contain at least one valid term"},
        )

    def test_search_matches_property_name_and_cadastral(self):
        self.assertEqual(
            [item["token"] for item in self._search("Casal").data["results"]],
            ["PR-002"],
        )
        self.assertEqual(
            [item["token"] for item in self._search("CAD-999").data["results"]],
            ["PR-002"],
        )

    def test_inactive_properties_are_excluded(self):
        self.assertNotIn(
            "PR-OFF",
            [item["token"] for item in self._search("Major").data["results"]],
        )

    def test_search_is_required(self):
        response = self.client.get(reverse("properties-ov"))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Search is required"})

    def test_search_requires_at_least_three_characters(self):
        response = self._search("Ma")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {"error": "Search must be at least 3 characters"},
        )

    def test_results_use_pagination_envelope(self):
        response = self._search("08001")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.data),
            {"count", "page", "limit", "total_pages", "results"},
        )
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(response.data["page"], 1)
        self.assertEqual(response.data["limit"], 20)
        self.assertEqual(response.data["total_pages"], 1)

    def test_invalid_page_returns_400(self):
        response = self._search("08001", page=99)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Invalid page"})

    def test_properties_requires_authentication(self):
        anonymous = APIClient()

        response = anonymous.get(reverse("properties-ov"), {"search": "Major"})

        self.assertEqual(response.status_code, 401)


class PersonDataOVTests(TestCase):
    """`GET /ov/person-data/?dni=` — dades de contacte de la persona
    identificada pel DNI, sense contracte, incloent-hi les files inactives."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="ov-person-data-test", password="not-used"
        )
        cls.dni = "12345678A"
        cls.person = Person.objects.create(
            token=cls.dni, name="Anna", surname="Garcia"
        )
        cls.default_contact = PersonContact.objects.create(
            token="CONTACT-1",
            person=cls.person,
            phone="600123456",
            email="anna.garcia@example.com",
            role="PARTICULAR",
        )
        cls.inactive_phone = PersonContact.objects.create(
            token="CONTACT-2",
            person=cls.person,
            phone="600999888",
            role="MÒBIL",
            is_active=False,
        )
        cls.email_only = PersonContact.objects.create(
            token="CONTACT-3",
            person=cls.person,
            email="altre@example.com",
            role="ALTRES",
        )
        cls.empty_contact = PersonContact.objects.create(
            token="CONTACT-4", person=cls.person, phone=None, email=""
        )

        street_type = StreetType.objects.create(abbreviation="C", name="Carrer")
        city = City.objects.create(token="CITY-PERSON", name="Barcelona")
        country = Country.objects.create(name="Espanya", iso_code="ES")
        street = Street.objects.create(
            name="Major", type=street_type, city=city
        )
        number = StreetNumber.objects.create(street=street, number=123)
        cls.address = Address.objects.create(
            token="ADDRESS-1",
            street=street,
            street_number=number,
            city=city,
            country=country,
            postal_code="08001",
            floor="2",
            door="B",
        )
        cls.billing_address = PersonAddress.objects.create(
            token="PADDRESS-1",
            person=cls.person,
            address=cls.address,
            attention_to="Anna Garcia",
            is_billing=True,
            is_active=True,
        )
        cls.inactive_address = PersonAddress.objects.create(
            token="PADDRESS-2",
            person=cls.person,
            address=None,
            is_billing=False,
            is_active=False,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _get(self, dni=None):
        params = {} if dni is None else {"dni": dni}
        return self.client.get(reverse("person-data-ov"), params)

    def test_returns_person_phones_emails_and_addresses(self):
        response = self._get(self.dni)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.data), {"person", "phones", "emails", "addresses"}
        )
        self.assertEqual(
            response.data["person"],
            {
                "token": self.dni,
                "name": "Anna",
                "surname": "Garcia",
                "is_juridic": False,
            },
        )

    def test_phones_include_inactive_and_exclude_empty_rows(self):
        response = self._get(self.dni)

        phones = response.data["phones"]
        self.assertEqual(
            [item["token"] for item in phones],
            ["CONTACT-1", "CONTACT-2"],
        )
        self.assertTrue(phones[0]["is_default"])
        self.assertFalse(phones[1]["is_active"])

    def test_emails_include_inactive_and_exclude_empty_rows(self):
        response = self._get(self.dni)

        emails = response.data["emails"]
        self.assertEqual(
            [item["token"] for item in emails],
            ["CONTACT-1", "CONTACT-3"],
        )
        self.assertTrue(emails[0]["is_default"])

    def test_contact_with_phone_and_email_appears_in_both_lists(self):
        response = self._get(self.dni)

        phone_tokens = [item["token"] for item in response.data["phones"]]
        email_tokens = [item["token"] for item in response.data["emails"]]
        self.assertIn("CONTACT-1", phone_tokens)
        self.assertIn("CONTACT-1", email_tokens)

    def test_addresses_include_inactive_and_null_address(self):
        response = self._get(self.dni)

        addresses = response.data["addresses"]
        self.assertEqual(
            [item["token"] for item in addresses],
            ["PADDRESS-1", "PADDRESS-2"],
        )
        billing = addresses[0]
        self.assertTrue(billing["is_billing"])
        self.assertTrue(billing["is_active"])
        self.assertEqual(billing["address"], str(self.address))
        self.assertEqual(billing["street"], "C. Major")
        self.assertEqual(billing["street_number"], "123")
        self.assertEqual(billing["postal_code"], "08001")
        self.assertEqual(billing["city"], "Barcelona")
        self.assertEqual(billing["floor"], "2")
        self.assertEqual(billing["door"], "B")
        self.assertEqual(billing["attention_to"], "Anna Garcia")
        inactive = addresses[1]
        self.assertFalse(inactive["is_active"])
        self.assertFalse(inactive["is_billing"])
        self.assertIsNone(inactive["address"])
        self.assertIsNone(inactive["street"])
        self.assertIsNone(inactive["postal_code"])

    def test_dni_is_normalized(self):
        response = self._get(f"  {self.dni.lower()} ")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["person"]["token"], self.dni)

    def test_dni_is_required(self):
        response = self._get()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "DNI is required"})

    def test_unknown_dni_returns_404(self):
        response = self._get("99999999X")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Person not found"})

    def test_person_data_requires_authentication(self):
        anonymous = APIClient()

        response = anonymous.get(
            reverse("person-data-ov"), {"dni": self.dni}
        )

        self.assertEqual(response.status_code, 401)

    def test_endpoint_uses_dedicated_throttle(self):
        self.assertEqual(PersonDataOVView.throttle_classes, [PersonDataThrottle])
        self.assertEqual(PersonDataThrottle.rate, "35/min")
        self.assertEqual(PersonDataThrottle.scope, "ov_person_data_dni")

    def test_token_is_matched_case_insensitively(self):
        person = Person.objects.create(token="87654321z", name="Bea")
        PersonContact.objects.create(
            token="LOWERCASE-1", person=person, phone="611000111"
        )

        response = self._get("87654321Z")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["person"]["token"], "87654321z")
        self.assertEqual(
            [item["phone"] for item in response.data["phones"]],
            ["611000111"],
        )

    def test_spaces_hyphens_and_dots_are_ignored(self):
        person = Person.objects.create(token="12345678-Z", name="Carla")
        PersonContact.objects.create(
            token="HYPHEN-1", person=person, phone="622000222"
        )

        for dni in ("12345678Z", "12345678-Z", " 1234.5678-Z "):
            with self.subTest(dni=dni):
                response = self._get(dni)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.data["person"]["token"], "12345678-Z"
                )

    def test_bank_account_dni_does_not_expose_another_person(self):
        payer = Person.objects.create(token="PAYER-TOKEN", name="Payer")
        PersonContact.objects.create(
            token="PAYER-CONTACT-1", person=payer, phone="633000333"
        )
        PersonBank.objects.create(
            person=payer,
            dni=" Y7654-321.Q ",
            iban="ES9121000418450200051332",
        )

        response = self._get("y7654321q")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Person not found"})

    def test_payer_with_matching_person_token_can_access_contacts(self):
        payer = Person.objects.create(token=" Y7654-321.Q ", name="Payer")
        PersonContact.objects.create(
            token="PAYER-CONTACT-1", person=payer, phone="633000333"
        )
        PersonBank.objects.create(
            person=payer, dni="Y7654321Q", iban="ES9121000418450200051332"
        )

        response = self._get("y7654321q")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["person"]["token"], payer.token)
        self.assertEqual(
            [item["phone"] for item in response.data["phones"]],
            ["633000333"],
        )

    def test_duplicate_token_prefers_person_with_contacts(self):
        Person.objects.create(token="11111111H", name="Sense")
        with_contacts = Person.objects.create(
            token="11111111H", name="Amb", surname="Contactes"
        )
        PersonContact.objects.create(
            token="DUPLICATE-1", person=with_contacts, phone="644000444"
        )

        response = self._get("11111111H")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["person"]["name"], "Amb")
        self.assertEqual(
            [item["phone"] for item in response.data["phones"]],
            ["644000444"],
        )


class InvoicePDFOVTests(TestCase):
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
        cls.user = User.objects.create_user(username="ov-invoice-pdf-test")
        for token, value in (
            ("contract_termination_completed_token", "3"),
            ("contract_terminated_status", "-1"),
            ("invoice_type_invoice_token", "F"),
            ("invoice_status_cancelled_token", "-6"),
        ):
            ConfigProject.objects.update_or_create(
                token=token, defaults={"value": value}
            )
        cls.contract = Contract.objects.create(token="PDF-CONTRACT")
        cls.invoice = Invoice.objects.create(
            token="PDF-INVOICE",
            serie_final="FC/2026/1",
            contract=cls.contract,
            type_final="F",
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _get(self, **overrides):
        params = {
            "contract_token": self.contract.token,
            "invoice_token": self.invoice.token,
        }
        params.update(overrides)
        return self.client.get(reverse("invoice-pdf-ov"), params)

    def test_reuses_stored_pdf_without_generating_or_replacing_it(self):
        pdf_bytes = b"%PDF-1.4 stored invoice"
        path = os.path.join(self._storage_dir, "stored.pdf")
        with open(path, "wb") as stored:
            stored.write(pdf_bytes)
        document = Document.objects.create(
            entity_id=self.invoice.pk,
            service="hdd",
            location=path,
            document_name="original.pdf",
        )
        Invoice.objects.filter(pk=self.invoice.pk).update(invoice_file=document)
        document_count = Document.objects.count()

        with patch("ov.views.generate_report_invoice_pdf") as generate:
            response = self._get(invoice_token=self.invoice.serie_final)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(base64.b64decode(response.data["pdf"]), pdf_bytes)
        self.assertEqual(response.data["document_name"], "original.pdf")
        generate.assert_not_called()
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.invoice_file_id, document.pk)
        self.assertEqual(Document.objects.count(), document_count)
        with open(path, "rb") as stored:
            self.assertEqual(stored.read(), pdf_bytes)

    def test_missing_invoice_type_config_returns_not_found(self):
        ConfigProject.objects.filter(token="invoice_type_invoice_token").delete()

        response = self._get()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Invoice not found"})

    def test_generates_missing_pdf_in_memory_with_fallback_document_name(self):
        for serie_final in ("FC/2026/1", None):
            with self.subTest(serie_final=serie_final):
                Invoice.objects.filter(pk=self.invoice.pk).update(
                    serie_final=serie_final
                )
                document_count = Document.objects.count()
                with patch(
                    "ov.views.generate_report_invoice_pdf",
                    return_value=(None, None, BytesIO(b"%PDF-1.4 generated")),
                ) as generate:
                    response = self._get()

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    base64.b64decode(response.data["pdf"]), b"%PDF-1.4 generated"
                )
                expected_name = (
                    f"invoice_{serie_final or self.invoice.token}_{self.invoice.pk}.pdf"
                )
                self.assertEqual(response.data["filename"], expected_name)
                self.assertEqual(response.data["document_name"], expected_name)
                generate.assert_called_once()
                self.assertIs(generate.call_args.kwargs["save_pdf"], False)
                self.invoice.refresh_from_db()
                self.assertIsNone(self.invoice.invoice_file_id)
                self.assertEqual(Document.objects.count(), document_count)

    def test_unavailable_stored_pdf_falls_back_without_replacing_document(self):
        document = Document.objects.create(
            entity_id=self.invoice.pk,
            service="hdd",
            document_name="unavailable.pdf",
        )
        Invoice.objects.filter(pk=self.invoice.pk).update(invoice_file=document)
        document_count = Document.objects.count()

        with patch(
            "ov.views.generate_report_invoice_pdf",
            return_value=(None, None, BytesIO(b"%PDF-1.4 fallback")),
        ) as generate:
            response = self._get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(base64.b64decode(response.data["pdf"]), b"%PDF-1.4 fallback")
        self.assertEqual(response.data["document_name"], response.data["filename"])
        generate.assert_called_once()
        self.assertIs(generate.call_args.kwargs["save_pdf"], False)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.invoice_file_id, document.pk)
        self.assertEqual(Document.objects.count(), document_count)

    def _batch_download(self):
        return self.client.post(
            reverse("batch-invoice-download-ov"),
            {"invoice_tokens": [self.invoice.token]},
            format="json",
            QUERY_STRING=f"contract_token={self.contract.token}",
        )

    def test_batch_download_reuses_stored_pdf(self):
        pdf_bytes = b"%PDF-1.4 archived batch invoice"
        path = os.path.join(self._storage_dir, "batch.pdf")
        with open(path, "wb") as stored:
            stored.write(pdf_bytes)
        document = Document.objects.create(
            entity_id=self.invoice.pk, service="hdd", location=path,
            document_name="batch.pdf",
        )
        Invoice.objects.filter(pk=self.invoice.pk).update(invoice_file=document)
        document_count = Document.objects.count()

        with patch("ov.views.generate_report_invoice_pdf") as generate:
            response = self._batch_download()

        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(BytesIO(b"".join(response.streaming_content))) as archive:
            self.assertEqual(archive.namelist(), ["factura_FC-2026-1.pdf"])
            self.assertEqual(archive.read("factura_FC-2026-1.pdf"), pdf_bytes)
        generate.assert_not_called()
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.invoice_file_id, document.pk)
        self.assertEqual(Document.objects.count(), document_count)

    def test_batch_download_generates_pdf_when_no_archive_exists(self):
        with patch(
            "ov.views.generate_report_invoice_pdf",
            return_value=(None, None, BytesIO(b"generated batch")),
        ) as generate:
            response = self._batch_download()

        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(BytesIO(b"".join(response.streaming_content))) as archive:
            self.assertEqual(archive.read("factura_FC-2026-1.pdf"), b"generated batch")
        generate.assert_called_once()
        self.assertIs(generate.call_args.kwargs["save_pdf"], False)
        self.invoice.refresh_from_db()
        self.assertIsNone(self.invoice.invoice_file_id)

    def test_batch_download_falls_back_when_archive_is_unavailable(self):
        document = Document.objects.create(entity_id=self.invoice.pk, service="hdd")
        Invoice.objects.filter(pk=self.invoice.pk).update(invoice_file=document)
        document_count = Document.objects.count()

        for download_result in (None, FileNotFoundError("missing archive")):
            with self.subTest(download_result=download_result):
                download_kwargs = (
                    {"side_effect": download_result}
                    if isinstance(download_result, Exception)
                    else {"return_value": download_result}
                )
                with patch("ov.views.download_document", **download_kwargs), patch(
                    "ov.views.generate_report_invoice_pdf",
                    return_value=(None, None, BytesIO(b"fallback batch")),
                ) as generate:
                    response = self._batch_download()

                self.assertEqual(response.status_code, 200)
                with zipfile.ZipFile(BytesIO(b"".join(response.streaming_content))) as archive:
                    self.assertEqual(
                        archive.read("factura_FC-2026-1.pdf"), b"fallback batch"
                    )
                generate.assert_called_once()
                self.assertIs(generate.call_args.kwargs["save_pdf"], False)
                self.invoice.refresh_from_db()
                self.assertEqual(self.invoice.invoice_file_id, document.pk)
                self.assertEqual(Document.objects.count(), document_count)


class QuickPayOVTests(TestCase):
    """`POST /ov/invoice/quick-pay/` — resolució sense escriptures d'una
    factura a partir de número de contracte, número de factura (`serie_final`)
    i import exacte (`total_final`)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="ov-quick-pay-test", password="not-used"
        )

        for token, value in (
            ("contract_termination_completed_token", "3"),
            ("contract_terminated_status", "-1"),
            ("bail_status_returned_token", "-1"),
            ("payment_status_paid_token", "0"),
            ("invoice_type_invoice_token", "F"),
            ("invoice_status_paid_token", "0"),
            ("invoice_status_pending_token", "1"),
            ("invoice_status_cancelled_token", "-6"),
            ("invoice_status_dropped_token", "-7"),
            ("invoice_status_payoff_token", "-2"),
            ("invoice_status_irrecoverable_token", "-5"),
            (
                "invoice_status_part_irrecoverable_token",
                "-4",
            ),
        ):
            ConfigProject.objects.update_or_create(
                token=token, defaults={"value": value}
            )

        cls.paid_payment_status, _ = PaymentStatus.objects.get_or_create(
            token="0", defaults={"name": "Pagat"}
        )
        cls.holder = Person.objects.create(
            token="12345678A", name="Test", surname="QuickPay"
        )
        cls.contract = Contract.objects.create(
            token="QP-CONTRACT-1", holder=cls.holder
        )

        statuses = {}
        for token, name in (
            ("2", "Confirmada"),
            ("3", "Enviada"),
            ("-1", "Vençuda"),
            ("-3", "Morositat"),
            ("4", "En compromís"),
            ("0", "Pagada"),
            ("1", "Prefactura"),
            ("-6", "Abonada"),
            ("-7", "Anul·lada"),
            ("-2", "Abonament"),
            ("-5", "Irrecuperable"),
            ("-4", "Parcialment Irrecuperable"),
        ):
            statuses[token], _ = InvoiceStatus.objects.get_or_create(
                token=token, defaults={"name": name}
            )
        cls.statuses = statuses

        cls.payable = cls._create_invoice(
            token="QP-INV-1",
            serie_final="FC/202609/000001",
            type_final="F",
            total="101.73",
            left_to_pay="101.73",
            status=statuses["3"],
        )
        cls.second_payable = cls._create_invoice(
            token="QP-INV-2",
            serie_final="FC/202609/000002",
            type_final="F",
            total="50.00",
            left_to_pay="50.00",
            status=statuses["2"],
        )
        cls.proforma = cls._create_invoice(
            token="QP-INV-3",
            serie_final="PF/202609/000003",
            type_final="P",
            total="50.00",
            left_to_pay="50.00",
            status=statuses["3"],
        )
        cls.non_payable_invoices = {}
        for index, status_token in enumerate(
            ("0", "1", "-6", "-7", "-2", "-5", "-4"), start=10
        ):
            cls.non_payable_invoices[status_token] = cls._create_invoice(
                token=f"QP-INV-{index}",
                serie_final=f"FC/202609/00{index:04d}",
                type_final="F",
                total="30.00",
                left_to_pay="30.00",
                status=statuses[status_token],
            )
        cls.zero_left = cls._create_invoice(
            token="QP-INV-20",
            serie_final="FC/202609/000020",
            type_final="F",
            total="15.00",
            left_to_pay="0.00",
            status=statuses["3"],
        )
        cls.without_status = cls._create_invoice(
            token="QP-INV-21",
            serie_final="FC/202609/000021",
            type_final="F",
            total="10.00",
            left_to_pay="10.00",
            status=None,
        )

    @classmethod
    def _create_invoice(
        cls, token, serie_final, type_final, total, left_to_pay, status
    ):
        invoice = Invoice.objects.create(
            token=token,
            contract=cls.contract,
            serie_final=serie_final,
            type_final=type_final,
            total_final=Decimal(total),
            left_to_pay=Decimal(left_to_pay),
            status=status,
            issue_date=date(2026, 9, 1),
            due_date=date(2026, 9, 30),
        )
        Payment.objects.create(invoice=invoice, amount=Decimal(left_to_pay))
        return invoice

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _payload(self, **overrides):
        payload = {
            "contract_number": "QP-CONTRACT-1",
            "invoice_number": "FC/202609/000001",
            "amount": "101.73",
        }
        payload.update(overrides)
        return payload

    def _post(self, **overrides):
        return self.client.post(
            reverse("quick-pay-ov"), self._payload(**overrides), format="json"
        )

    def test_resolves_invoice_without_writes(self):
        invoice_count = Invoice.objects.count()
        payment_count = self.payable.payments.count()

        response = self._post()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["contract_token"], "QP-CONTRACT-1")
        self.assertEqual(response.data["invoice_token"], "QP-INV-1")
        self.assertEqual(response.data["invoice_number"], "FC/202609/000001")
        self.assertEqual(response.data["issue_date"], "2026-09-01")
        self.assertEqual(response.data["due_date"], "2026-09-30")
        self.assertEqual(response.json()["invoice_amount"], 101.73)
        self.assertEqual(response.json()["left_to_pay"], 101.73)
        self.assertEqual(
            response.data["status"],
            {
                "token": self.statuses["3"].token,
                "name": self.statuses["3"].name,
            },
        )
        self.assertTrue(response.data["payable"])

        self.assertEqual(Invoice.objects.count(), invoice_count)
        self.assertEqual(self.payable.payments.count(), payment_count)

    def test_input_is_trimmed(self):
        response = self._post(
            contract_number="  QP-CONTRACT-1  ",
            invoice_number="  FC/202609/000001  ",
            amount=" 101.73 ",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["invoice_token"], "QP-INV-1")

    def test_amount_is_matched_exactly(self):
        response = self._post(amount="101.74")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Invoice not found"})

    def test_unknown_contract_returns_uniform_404(self):
        response = self._post(contract_number="QP-CONTRACT-UNKNOWN")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Invoice not found"})

    def test_unknown_invoice_number_returns_uniform_404(self):
        response = self._post(invoice_number="FC/202609/999999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Invoice not found"})

    def test_invoice_number_is_matched_by_serie_final_not_token(self):
        response = self._post(invoice_number="QP-INV-1")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Invoice not found"})

    def test_proforma_is_not_resolved(self):
        response = self._post(
            invoice_number="PF/202609/000003", amount="50.00"
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Invoice not found"})

    def test_non_payable_statuses_return_409(self):
        for status_token, invoice in self.non_payable_invoices.items():
            with self.subTest(status=status_token):
                response = self._post(
                    invoice_number=invoice.serie_final, amount="30.00"
                )

                self.assertEqual(response.status_code, 409)
                self.assertEqual(
                    response.data["error"], "Invoice is not payable"
                )
                self.assertEqual(
                    response.data["status"]["token"], status_token
                )
                self.assertEqual(response.json()["left_to_pay"], 30.00)

    def test_zero_left_to_pay_returns_409(self):
        response = self._post(
            invoice_number="FC/202609/000020", amount="15.00"
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"], "Invoice is not payable")
        self.assertEqual(response.json()["left_to_pay"], 0)

    def test_missing_or_empty_paid_status_config_returns_409(self):
        for value in (None, ""):
            with self.subTest(value=value):
                config = ConfigProject.objects.filter(token="invoice_status_paid_token")
                if value is None:
                    config.delete()
                else:
                    ConfigProject.objects.create(
                        token="invoice_status_paid_token", value=value
                    )

                response = self._post()

                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.data["error"], "Invoice is not payable")

    def test_invoice_without_payment_returns_409(self):
        self.payable.payments.all().delete()

        response = self._post()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"], "Invoice is not payable")
        self.assertFalse(self.payable.payments.exists())

    def test_missing_empty_or_unknown_paid_payment_status_config_returns_409(self):
        payment_ids = list(self.payable.payments.values_list("pk", flat=True))
        for value in (None, "", "unknown-payment-status"):
            with self.subTest(value=value):
                ConfigProject.objects.filter(token="payment_status_paid_token").delete()
                if value is not None:
                    ConfigProject.objects.create(token="payment_status_paid_token", value=value)

                response = self._post()

                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.data["error"], "Invoice is not payable")
                self.assertEqual(list(self.payable.payments.values_list("pk", flat=True)), payment_ids)

        ConfigProject.objects.update_or_create(
            token="payment_status_paid_token", defaults={"value": "0"}
        )
        self.assertEqual(self._post().status_code, 200)
        self.assertEqual(list(self.payable.payments.values_list("pk", flat=True)), payment_ids)

    def test_missing_paid_payment_status_row_blocks_until_restored(self):
        self.paid_payment_status.delete()
        self.assertEqual(self._post().status_code, 409)

        PaymentStatus.objects.create(token="0", name="Pagat")
        self.assertEqual(self._post().status_code, 200)

    def test_only_paid_payments_return_409_even_with_stale_invoice_balance(self):
        paid_status = PaymentStatus.objects.create(token="SETTLED", name="Pagat")
        ConfigProject.objects.filter(token="payment_status_paid_token").update(value="SETTLED")
        self.payable.payments.update(status=paid_status)
        Payment.objects.create(invoice=self.payable, amount=Decimal("1.00"), status=paid_status)

        response = self._post()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"], "Invoice is not payable")
        self.assertEqual(response.json()["left_to_pay"], 101.73)

    def test_mixed_paid_and_unpaid_payments_remain_payable(self):
        Payment.objects.create(
            invoice=self.payable, amount=Decimal("1.00"), status=self.paid_payment_status
        )

        self.assertEqual(self._post().status_code, 200)

    def test_null_left_to_pay_returns_409_with_null_amount(self):
        Invoice.objects.filter(pk=self.payable.pk).update(left_to_pay=None)

        response = self._post()

        self.assertEqual(response.status_code, 409)
        self.assertIsNone(response.json()["left_to_pay"])

    def test_invoice_without_status_returns_409(self):
        response = self._post(
            invoice_number="FC/202609/000021", amount="10.00"
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"], "Invoice is not payable")
        self.assertIsNone(response.data["status"])

    def test_other_payable_invoices_can_be_resolved(self):
        response = self._post(
            invoice_number="FC/202609/000002", amount="50.00"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["invoice_token"], "QP-INV-2")

    def test_more_than_two_decimals_returns_400(self):
        response = self._post(amount="101.731")

        self.assertEqual(response.status_code, 400)
        self.assertIn("amount", response.data)

    def test_negative_amount_returns_400(self):
        response = self._post(amount="-101.73")

        self.assertEqual(response.status_code, 400)
        self.assertIn("amount", response.data)

    def test_missing_fields_return_400(self):
        response = self.client.post(reverse("quick-pay-ov"), {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("contract_number", response.data)
        self.assertIn("invoice_number", response.data)
        self.assertIn("amount", response.data)

    def test_quick_pay_requires_authentication(self):
        anonymous = APIClient()

        response = anonymous.post(
            reverse("quick-pay-ov"), self._payload(), format="json"
        )

        self.assertEqual(response.status_code, 401)

    def test_endpoint_uses_dedicated_throttle(self):
        self.assertEqual(QuickPayOVView.throttle_classes, [QuickPayThrottle])
        self.assertEqual(QuickPayThrottle.rate, "35/min")
        self.assertEqual(QuickPayThrottle.scope, "ov_quick_pay")


class PaymentReceiptOVTests(TestCase):
    """`GET /ov/payment-receipt/` — justificant de pagament en PDF per a
    pagaments en efectiu o amb targeta al TPV físic, lligat al contracte i al
    DNI del pagador/titular."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="ov-payment-receipt-test", password="not-used"
        )

        for token, value in (
            ("contract_termination_completed_token", "3"),
            ("contract_terminated_status", "-1"),
            ("bail_status_returned_token", "-1"),
            ("payment_status_paid_token", "0"),
            ("invoice_status_paid_token", "0"),
            ("invoice_status_cancelled_token", "-6"),
            ("invoice_type_invoice_token", "F"),
        ):
            ConfigProject.objects.update_or_create(
                token=token, defaults={"value": value}
            )

        cls.company = Company.objects.create(
            name="Aigua Test", vat="B12345678"
        )
        cls.exploitation = Exploitation.objects.create(
            token="EXP-RECEIPT-1",
            name="Explotació Test",
            company=cls.company,
            is_active=True,
        )

        cls.holder = Person.objects.create(
            token="12345678A", name="Anna", surname="Titular"
        )
        cls.other_holder = Person.objects.create(
            token="11111111A", name="Bernat", surname="Altre"
        )
        cls.contract = Contract.objects.create(
            token="RECEIPT-CONTRACT-1", holder=cls.holder
        )
        cls.other_contract = Contract.objects.create(
            token="RECEIPT-CONTRACT-2", holder=cls.other_holder
        )

        cls.paid_status, _ = PaymentStatus.objects.get_or_create(
            token="0", defaults={"name": "Pagat"}
        )
        cls.pending_status, _ = PaymentStatus.objects.get_or_create(
            token="1", defaults={"name": "Pendent"}
        )
        cls.invoice_status, _ = InvoiceStatus.objects.get_or_create(
            token="3", defaults={"name": "Enviada"}
        )

        cls.invoice = cls._create_invoice(
            token="RECEIPT-INV-1",
            serie_final="FC/202609/010001",
            type_final="F",
            contract=cls.contract,
        )
        cls.payment = cls._create_payment(
            token="PAY-CASH-1",
            invoice=cls.invoice,
            payment_type_token="CASH",
            status=cls.paid_status,
            payer="12345678A",
        )

        cls.card_invoice = cls._create_invoice(
            token="RECEIPT-INV-2",
            serie_final="FC/202609/010002",
            type_final="F",
            contract=cls.contract,
        )
        cls.card_payment = cls._create_payment(
            token="PAY-CARD-1",
            invoice=cls.card_invoice,
            payment_type_token="CARD",
            status=cls.paid_status,
            payer="12345678A",
        )

        cls.online_invoice = cls._create_invoice(
            token="RECEIPT-INV-3",
            serie_final="FC/202609/010003",
            type_final="F",
            contract=cls.contract,
        )
        cls.online_payment = cls._create_payment(
            token="PAY-ONLINE-1",
            invoice=cls.online_invoice,
            payment_type_token="TPV_ONLINE",
            status=cls.paid_status,
            payer="12345678A",
        )

        cls.debit_invoice = cls._create_invoice(
            token="RECEIPT-INV-4",
            serie_final="FC/202609/010004",
            type_final="F",
            contract=cls.contract,
        )
        cls.debit_payment = cls._create_payment(
            token="PAY-DEBIT-1",
            invoice=cls.debit_invoice,
            payment_type_token="DIRECT_DEBIT",
            status=cls.paid_status,
            payer="12345678A",
        )
        cls.transfer_payment = cls._create_payment(
            token="PAY-TRANSFER-1",
            invoice=cls.debit_invoice,
            payment_type_token="BANK_TRANSFER",
            status=cls.paid_status,
            payer="12345678A",
        )

        cls.unpaid_invoice = cls._create_invoice(
            token="RECEIPT-INV-5",
            serie_final="FC/202609/010005",
            type_final="F",
            contract=cls.contract,
        )
        cls.unpaid_payment = cls._create_payment(
            token="PAY-UNPAID-1",
            invoice=cls.unpaid_invoice,
            payment_type_token="CASH",
            status=cls.pending_status,
            payer="12345678A",
        )

        cls.other_invoice = cls._create_invoice(
            token="RECEIPT-INV-6",
            serie_final="FC/202609/010006",
            type_final="F",
            contract=cls.other_contract,
        )
        cls.other_payment = cls._create_payment(
            token="PAY-OTHER-1",
            invoice=cls.other_invoice,
            payment_type_token="CASH",
            status=cls.paid_status,
            payer="11111111A",
        )

        cls.proforma_invoice = cls._create_invoice(
            token="RECEIPT-INV-7",
            serie_final="PF/202609/010007",
            type_final="P",
            contract=cls.contract,
        )
        cls.proforma_payment = cls._create_payment(
            token="PAY-PROFORMA-1",
            invoice=cls.proforma_invoice,
            payment_type_token="CASH",
            status=cls.paid_status,
            payer="12345678A",
        )

        cls.invoiceless_payment = cls._create_payment(
            token="PAY-NOINVOICE-1",
            invoice=None,
            payment_type_token="CASH",
            status=cls.paid_status,
            payer="12345678A",
        )

        iban_holder = Person.objects.create(token="87654321Z", name="Carla")
        cls.person_bank = PersonBank.objects.create(
            token="RECEIPT-BANK-1",
            person=iban_holder,
            dni="87654321-Z",
            iban="ES12345678901234567890",
        )
        cls.general_payment = GeneralPayment.objects.create(
            token="RECEIPT-GP-1",
            type=PaymentType.objects.filter(token="DIRECT_DEBIT").first(),
            IBAN=cls.person_bank,
        )
        cls.iban_contract = Contract.objects.create(
            token="RECEIPT-CONTRACT-3",
            holder=cls.other_holder,
            payment=cls.general_payment,
        )
        cls.iban_invoice = cls._create_invoice(
            token="RECEIPT-INV-8",
            serie_final="FC/202609/010008",
            type_final="F",
            contract=cls.iban_contract,
        )
        cls.iban_payment = cls._create_payment(
            token="PAY-IBAN-1",
            invoice=cls.iban_invoice,
            payment_type_token="CASH",
            status=cls.paid_status,
            payer="22222222B",
        )

    @classmethod
    def _create_invoice(cls, token, serie_final, type_final, contract):
        return Invoice.objects.create(
            token=token,
            contract=contract,
            serie_final=serie_final,
            type_final=type_final,
            total_final=Decimal("40.00"),
            left_to_pay=Decimal("0.00"),
            status=cls.invoice_status,
            exploitation=cls.exploitation,
            issue_date=date(2026, 9, 1),
            due_date=date(2026, 9, 30),
        )

    @classmethod
    def _create_payment(
        cls, token, invoice, payment_type_token, status, payer
    ):
        return Payment.objects.create(
            token=token,
            status=status,
            invoice=invoice,
            contract=invoice.contract if invoice else cls.contract,
            payment_type=payment_type_token,
            payment_type_token=payment_type_token,
            amount=Decimal("40.00"),
            payment_date=date(2026, 9, 15),
            customer_token_final=payer,
            payer_token_final=payer,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _get(self, headers=None, **overrides):
        params = {
            "contract_token": "RECEIPT-CONTRACT-1",
            "payment_token": "PAY-CASH-1",
            "dni": "12345678A",
        }
        params.update(overrides)
        return self.client.get(
            reverse("payment-receipt-ov"), params, **(headers or {})
        )

    def _get_with_mocked_pdf(self, headers=None, **overrides):
        captured = {}

        def fake_render(payments, request, **kwargs):
            captured["active_language"] = translation.get_language()
            captured["language"] = kwargs.get("language")
            captured["observation"] = kwargs.get("observation")
            return BytesIO(b"%PDF-1.4 mocked"), "receipt.pdf"

        with patch(
            "billing.utils.payment_proof_service.render_payment_proof_pdf",
            side_effect=fake_render,
        ):
            response = self._get(headers=headers, **overrides)
        return response, captured

    def _pdf_bytes(self, response):
        return base64.b64decode(response.data["pdf_base64"], validate=True)

    def test_cash_receipt_returns_base64_pdf_without_writes(self):
        response = self._get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertNotIn("Content-Disposition", response)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response["Content-Language"], "ca")
        self.assertIn("pdf_base64", response.data)
        self.assertTrue(self._pdf_bytes(response).startswith(b"%PDF"))

        self.payment.refresh_from_db()
        self.assertIsNone(self.payment.document)

    def test_card_receipt_returns_base64_pdf(self):
        response = self._get(payment_token="PAY-CARD-1")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self._pdf_bytes(response).startswith(b"%PDF"))

    def test_dni_is_normalized(self):
        response = self._get(dni=" 1234.5678-a ")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self._pdf_bytes(response).startswith(b"%PDF"))

    def test_iban_holder_dni_is_accepted(self):
        response = self._get(
            contract_token="RECEIPT-CONTRACT-3",
            payment_token="PAY-IBAN-1",
            dni=" 87654321-z ",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self._pdf_bytes(response).startswith(b"%PDF"))

    def test_unknown_dni_returns_uniform_404(self):
        response = self._get(dni="99999999X")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Payment receipt not found"})

    def test_tpv_online_payment_returns_404(self):
        response = self._get(payment_token="PAY-ONLINE-1")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Payment receipt not found"})

    def test_direct_debit_and_transfer_return_404(self):
        for payment_token in ("PAY-DEBIT-1", "PAY-TRANSFER-1"):
            with self.subTest(payment_token=payment_token):
                response = self._get(payment_token=payment_token)

                self.assertEqual(response.status_code, 404)
                self.assertEqual(
                    response.data, {"error": "Payment receipt not found"}
                )

    def test_unpaid_payment_returns_404(self):
        response = self._get(payment_token="PAY-UNPAID-1")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Payment receipt not found"})

    def test_payment_of_another_contract_returns_404(self):
        response = self._get(
            contract_token="RECEIPT-CONTRACT-1",
            payment_token="PAY-OTHER-1",
            dni="11111111A",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Payment receipt not found"})

    def test_proforma_invoice_returns_404(self):
        response = self._get(payment_token="PAY-PROFORMA-1")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Payment receipt not found"})

    def test_payment_without_invoice_returns_404(self):
        response = self._get(payment_token="PAY-NOINVOICE-1")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Payment receipt not found"})

    def test_unknown_payment_token_returns_404(self):
        response = self._get(payment_token="PAY-UNKNOWN-1")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Payment receipt not found"})

    def test_dni_is_required(self):
        response = self._get(dni="")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "DNI is required"})

    def test_contract_and_payment_tokens_are_required(self):
        response = self.client.get(reverse("payment-receipt-ov"), {})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {"error": "Contract token and payment token are required"},
        )

    def test_receipt_requires_authentication(self):
        anonymous = APIClient()

        response = anonymous.get(
            reverse("payment-receipt-ov"),
            {
                "contract_token": "RECEIPT-CONTRACT-1",
                "payment_token": "PAY-CASH-1",
                "dni": "12345678A",
            },
        )

        self.assertEqual(response.status_code, 401)

    def test_lang_query_parameter_selects_spanish(self):
        response, captured = self._get_with_mocked_pdf(lang="es")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Language"], "es")
        self.assertEqual(captured["active_language"], "es")
        self.assertEqual(captured["language"], "es")

    def test_lang_accepts_region_and_case(self):
        for lang in ("ES", "es-ES", "es_ES"):
            with self.subTest(lang=lang):
                response, captured = self._get_with_mocked_pdf(lang=lang)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Language"], "es")
                self.assertEqual(captured["active_language"], "es")

    def test_accept_language_is_used_without_lang(self):
        response, captured = self._get_with_mocked_pdf(
            headers={"HTTP_ACCEPT_LANGUAGE": "es-ES,es;q=0.9"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Language"], "es")
        self.assertEqual(captured["active_language"], "es")
        self.assertEqual(captured["language"], "es")

    def test_lang_takes_precedence_over_accept_language(self):
        response, captured = self._get_with_mocked_pdf(
            lang="en", headers={"HTTP_ACCEPT_LANGUAGE": "es-ES,es;q=0.9"}
        )

        self.assertEqual(response["Content-Language"], "en")
        self.assertEqual(captured["active_language"], "en")

    def test_unsupported_lang_falls_back_to_accept_language(self):
        response, captured = self._get_with_mocked_pdf(
            lang="fr", headers={"HTTP_ACCEPT_LANGUAGE": "gl"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Language"], "gl")
        self.assertEqual(captured["active_language"], "gl")

    def test_language_defaults_to_catalan(self):
        response, captured = self._get_with_mocked_pdf()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Language"], "ca")
        self.assertEqual(captured["active_language"], "ca")
        self.assertEqual(captured["language"], "ca")

    def test_template_keeps_catalan_by_default_and_honours_receipt_language(self):
        from django.template import Context, Template

        with open(
            os.path.join(
                settings.BASE_DIR,
                "billing",
                "templates",
                "payment_proof_template.html",
            ),
            encoding="utf-8",
        ) as template_file:
            template = Template(template_file.read())

        catalan = template.render(Context({}))
        self.assertIn('<html lang="ca">', catalan)
        self.assertIn("<title>Justificant de pagament</title>", catalan)

        with translation.override("es"):
            admin_render = template.render(Context({}))
        self.assertIn('<html lang="ca">', admin_render)
        self.assertIn(
            "<title>Justificant de pagament</title>", admin_render
        )

        english = template.render(Context({"receipt_language": "en"}))
        self.assertIn('<html lang="en">', english)

    def test_endpoint_uses_dedicated_throttle(self):
        self.assertEqual(
            PaymentReceiptOVView.throttle_classes, [PaymentReceiptThrottle]
        )
        self.assertEqual(PaymentReceiptThrottle.rate, "35/min")
        self.assertEqual(PaymentReceiptThrottle.scope, "ov_payment_receipt")


class InvoiceReturnRequestOVTests(TestCase):
    """`POST /ov/invoice/return-request/` — obre una incidència automàtica per
    a una devolució sol·licitada per l'abonat, sense tocar l'estat de la
    factura ni cap pagament."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="ov-return-request-test", password="not-used"
        )

        for token, value in (
            ("contract_termination_completed_token", "3"),
            ("contract_terminated_status", "-1"),
            ("bail_status_returned_token", "-1"),
            ("payment_status_paid_token", "0"),
            ("payment_status_returned_token", "-2"),
            ("invoice_status_paid_token", "0"),
            ("invoice_status_confirmed_token", "2"),
            ("invoice_status_cancelled_token", "-6"),
            ("invoice_type_invoice_token", "F"),
        ):
            ConfigProject.objects.update_or_create(
                token=token, defaults={"value": value}
            )

        cls.paid_invoice_status, _ = InvoiceStatus.objects.get_or_create(
            token="0", defaults={"name": "Pagada"}
        )
        cls.confirmed_invoice_status, _ = (
            InvoiceStatus.objects.get_or_create(
                token="2", defaults={"name": "Confirmada"}
            )
        )
        cls.pending_invoice_status, _ = InvoiceStatus.objects.get_or_create(
            token="1", defaults={"name": "Pre-factura"}
        )

        cls.paid_payment_status, _ = PaymentStatus.objects.get_or_create(
            token="0", defaults={"name": "Pagat"}
        )
        cls.returned_payment_status, _ = PaymentStatus.objects.get_or_create(
            token="-2", defaults={"name": "Retornat"}
        )

        cls.open_incident_status, _ = IncidentStatus.objects.update_or_create(
            token="1",
            defaults={"name": "Oberta", "is_default": True, "position": 1},
        )
        IncidentStatus.objects.update_or_create(
            token="2",
            defaults={"name": "Tancada", "is_default": False, "position": 3},
        )
        cls.return_incident_type, _ = IncidentType.objects.update_or_create(
            token="reclamacio", defaults={"name": "Reclamació"}
        )

        cls.holder = Person.objects.create(
            token="12345678A", name="Anna"
        )
        cls.other_holder = Person.objects.create(
            token="11111111A", name="Bernat"
        )
        cls.contract = Contract.objects.create(
            token="RETURN-CONTRACT-1", holder=cls.holder
        )
        cls.other_contract = Contract.objects.create(
            token="RETURN-CONTRACT-2", holder=cls.other_holder
        )

        cls.invoice = cls._create_invoice(
            token="RETURN-INV-1", contract=cls.contract
        )
        cls._create_payment(
            token="RETURN-PAY-1",
            invoice=cls.invoice,
            status=cls.paid_payment_status,
        )

        cls.returned_invoice = cls._create_invoice(
            token="RETURN-INV-2", contract=cls.contract
        )
        cls._create_payment(
            token="RETURN-PAY-2",
            invoice=cls.returned_invoice,
            status=cls.returned_payment_status,
        )

        cls.unpaid_invoice = cls._create_invoice(
            token="RETURN-INV-3",
            contract=cls.contract,
            status=cls.confirmed_invoice_status,
            left_to_pay=Decimal("40.00"),
        )
        # Pagada (status '0') però amb `left_to_pay` obsolet positiu: el senyal
        # de pagaments actualitza l'estat sense re-sincronitzar `left_to_pay`.
        cls.stale_left_to_pay_invoice = cls._create_invoice(
            token="RETURN-INV-4",
            contract=cls.contract,
            left_to_pay=Decimal("10.00"),
        )
        cls._create_payment(
            token="RETURN-PAY-4",
            invoice=cls.stale_left_to_pay_invoice,
            status=cls.paid_payment_status,
        )
        # Pagada (status '0') amb `left_to_pay` NULL.
        cls.null_left_to_pay_invoice = cls._create_invoice(
            token="RETURN-INV-8",
            contract=cls.contract,
            left_to_pay=None,
        )
        cls._create_payment(
            token="RETURN-PAY-8",
            invoice=cls.null_left_to_pay_invoice,
            status=cls.paid_payment_status,
        )
        cls.proforma_invoice = cls._create_invoice(
            token="RETURN-INV-5", contract=cls.contract, type_final="P"
        )
        cls.prefactura_invoice = cls._create_invoice(
            token="RETURN-INV-6",
            contract=cls.contract,
            status=cls.pending_invoice_status,
        )
        cls.other_invoice = cls._create_invoice(
            token="RETURN-INV-7", contract=cls.other_contract
        )

    @classmethod
    def _create_invoice(
        cls,
        token,
        contract,
        status=None,
        type_final="F",
        left_to_pay=Decimal("0.00"),
    ):
        return Invoice.objects.create(
            token=token,
            contract=contract,
            serie_final=f"FC/202609/{token}",
            type_final=type_final,
            total_final=Decimal("40.00"),
            left_to_pay=left_to_pay,
            status=status or cls.paid_invoice_status,
            issue_date=date(2026, 9, 1),
            due_date=date(2026, 9, 30),
        )

    @classmethod
    def _create_payment(cls, token, invoice, status):
        return Payment.objects.create(
            token=token,
            status=status,
            invoice=invoice,
            contract=invoice.contract,
            payment_type="DIRECT_DEBIT",
            payment_type_token="DIRECT_DEBIT",
            amount=Decimal("40.00"),
            payment_date=date(2026, 9, 15),
            customer_token_final="12345678A",
            payer_token_final="12345678A",
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _post(self, **overrides):
        payload = {
            "invoice_token": "RETURN-INV-1",
            "contract_token": "RETURN-CONTRACT-1",
            "reason": "Domiciliació retornada pel banc",
        }
        payload.update(overrides)
        return self.client.post(
            reverse("invoice-return-request-ov"), payload, format="json"
        )

    def test_creates_open_incident_without_changing_invoice(self):
        payment_count = Payment.objects.count()
        movement_count = PaymentMovement.objects.count()
        remittance_return_count = PaymentRemittanceReturn.objects.count()
        status_id = self.invoice.status_id
        left_to_pay = self.invoice.left_to_pay

        response = self._post()

        self.assertEqual(response.status_code, 201)
        self.assertIn("incident_token", response.data)
        self.assertEqual(response.data["invoice_token"], "RETURN-INV-1")
        self.assertEqual(response.data["contract_token"], "RETURN-CONTRACT-1")
        self.assertEqual(response.data["status"]["token"], "1")
        self.assertEqual(response.data["type"]["token"], "reclamacio")

        incident = Incident.objects.get(
            token=response.data["incident_token"]
        )
        self.assertEqual(incident.invoice, self.invoice)
        self.assertEqual(incident.contract, self.contract)
        self.assertEqual(incident.type, self.return_incident_type)
        self.assertEqual(incident.status, self.open_incident_status)
        self.assertTrue(incident.is_active)
        self.assertEqual(
            incident.description, "Domiciliació retornada pel banc"
        )

        self.assertTrue(
            LogIncidentStatusChange.objects.filter(
                object=incident,
                current_status=self.open_incident_status,
                user=self.user,
            ).exists()
        )

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status_id, status_id)
        self.assertEqual(self.invoice.left_to_pay, left_to_pay)
        self.assertEqual(Payment.objects.count(), payment_count)
        self.assertEqual(PaymentMovement.objects.count(), movement_count)
        self.assertEqual(
            PaymentRemittanceReturn.objects.count(),
            remittance_return_count,
        )

    def test_generated_incident_token_collision_is_resolved(self):
        existing = Incident.objects.create(token="RETURN-COLLISION-0")

        with patch("ov.views.generate_token", return_value=existing.token):
            response = self._post()

        self.assertEqual(response.status_code, 201)
        self.assertNotEqual(response.data["incident_token"], existing.token)
        self.assertEqual(
            Incident.objects.filter(token=response.data["incident_token"]).count(), 1
        )
        existing.refresh_from_db()
        self.assertEqual(existing.token, "RETURN-COLLISION-0")

    def test_duplicate_request_returns_409_and_reuses_incident(self):
        first = self._post()
        second = self._post()

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(
            second.data["error"], "Return request already exists"
        )
        self.assertEqual(
            second.data["incident_token"], first.data["incident_token"]
        )
        self.assertEqual(
            Incident.objects.filter(invoice=self.invoice).count(), 1
        )

    def test_invoice_already_returned_by_bank_returns_409(self):
        response = self._post(invoice_token="RETURN-INV-2")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"], "Invoice already returned")
        self.assertEqual(
            Incident.objects.filter(invoice=self.returned_invoice).count(), 0
        )

    def test_unpaid_invoice_returns_409(self):
        response = self._post(invoice_token="RETURN-INV-3")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"], "Invoice is not paid")
        self.assertEqual(response.data["status"]["token"], "2")
        self.assertEqual(
            Incident.objects.filter(invoice=self.unpaid_invoice).count(), 0
        )

    def test_stale_left_to_pay_on_paid_invoice_is_accepted(self):
        # El senyal de pagaments marca la factura com a pagada però no
        # re-sincronitza `left_to_pay`, que pot quedar amb un valor positiu.
        # L'estat '0' (Pagada) és la font de veritat i no s'ha de bloquejar.
        self.assertEqual(
            self.stale_left_to_pay_invoice.left_to_pay, Decimal("10.00")
        )

        response = self._post(invoice_token="RETURN-INV-4")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["invoice_token"], "RETURN-INV-4")
        self.assertEqual(
            Incident.objects.filter(
                invoice=self.stale_left_to_pay_invoice
            ).count(),
            1,
        )

    def test_null_left_to_pay_on_paid_invoice_is_accepted(self):
        self.assertIsNone(self.null_left_to_pay_invoice.left_to_pay)

        response = self._post(invoice_token="RETURN-INV-8")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["invoice_token"], "RETURN-INV-8")
        self.assertEqual(
            Incident.objects.filter(
                invoice=self.null_left_to_pay_invoice
            ).count(),
            1,
        )

    def test_unknown_invoice_returns_uniform_404(self):
        response = self._post(invoice_token="RETURN-INV-UNKNOWN")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Invoice not found"})

    def test_proforma_and_prefactura_return_uniform_404(self):
        for invoice_token in ("RETURN-INV-5", "RETURN-INV-6"):
            with self.subTest(invoice_token=invoice_token):
                response = self._post(invoice_token=invoice_token)

                self.assertEqual(response.status_code, 404)
                self.assertEqual(
                    response.data, {"error": "Invoice not found"}
                )

    def test_invoice_of_another_contract_returns_uniform_404(self):
        wrong_contract = self._post(
            invoice_token="RETURN-INV-7",
            contract_token="RETURN-CONTRACT-1",
        )
        wrong_invoice = self._post(
            invoice_token="RETURN-INV-1",
            contract_token="RETURN-CONTRACT-2",
        )

        for response in (wrong_contract, wrong_invoice):
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.data, {"error": "Invoice not found"})

    def test_missing_fields_return_400(self):
        for overrides in (
            {"invoice_token": ""},
            {"contract_token": ""},
            {"reason": ""},
            {"reason": "   "},
        ):
            with self.subTest(overrides=overrides):
                response = self._post(**overrides)

                self.assertEqual(response.status_code, 400)

    def test_missing_config_returns_404(self):
        ConfigProject.objects.filter(
            token="invoice_type_invoice_token"
        ).delete()

        response = self._post()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Invoice not found"})

    def test_empty_invoice_type_config_returns_404_before_invoice_lookup(self):
        ConfigProject.objects.filter(token="invoice_type_invoice_token").update(
            value=""
        )

        with patch("ov.views.Invoice.objects.select_related") as lookup:
            response = self._post()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Invoice not found"})
        lookup.assert_not_called()

    def test_requires_authentication(self):
        anonymous = APIClient()

        response = anonymous.post(
            reverse("invoice-return-request-ov"),
            {
                "invoice_token": "RETURN-INV-1",
                "contract_token": "RETURN-CONTRACT-1",
                "reason": "Domiciliació retornada pel banc",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_endpoint_uses_dedicated_throttle(self):
        self.assertEqual(
            InvoiceReturnRequestOVView.throttle_classes,
            [ReturnRequestThrottle],
        )
        self.assertEqual(ReturnRequestThrottle.rate, "35/min")
        self.assertEqual(
            ReturnRequestThrottle.scope, "ov_invoice_return_request"
        )


class ContractProcedureOVTests(TestCase):
    """`POST /ov/procedures/contract/` — crea una sol·licitud d'alta de
    contracte (`ContractRequest`) en estat esborrany, sense crear cap
    contracte ni cap ordre, perquè atenció al client la finalitzi."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="ov-contract-procedure-test", password="not-used"
        )

        cls.default_status, _ = ContractRequestStatus.objects.update_or_create(
            token="1", defaults={"name": "Esborrany", "is_default": True}
        )
        ContractRequestStatus.objects.update_or_create(
            token="2", defaults={"name": "Pendent", "is_default": False}
        )
        ContractRequestStatus.objects.update_or_create(
            token="3", defaults={"name": "Finalitzat", "is_default": False}
        )
        cls.cancelled_status, _ = (
            ContractRequestStatus.objects.update_or_create(
                token="-1", defaults={"name": "Cancel·lat", "is_default": False}
            )
        )

        cls.procedure_type, _ = (
            ContractRequestType.objects.update_or_create(
                token="domestic",
                defaults={"name": "Domèstic", "is_active": True},
            )
        )
        cls.inactive_type, _ = (
            ContractRequestType.objects.update_or_create(
                token="industrial",
                defaults={"name": "Industrial", "is_active": False},
            )
        )

        cls.payment_type, _ = PaymentType.objects.update_or_create(
            token="DIRECT_DEBIT", defaults={"name": "Domiciliació bancària"}
        )
        cls.cash_payment_type, _ = PaymentType.objects.update_or_create(
            token="CASH", defaults={"name": "Efectiu"}
        )

        cls.tariff = PriceRate.objects.create(
            token="TR-CHOSEN", name="Tarifa triada", is_active=True
        )
        cls.type_tariff = PriceRate.objects.create(
            token="TR-TYPE", name="Tarifa del tipus", is_active=True
        )
        cls.inactive_tariff = PriceRate.objects.create(
            token="TR-OFF", name="Tarifa inactiva", is_active=False
        )
        cls.order_type = OrderType.objects.create(
            token="OT-ALTA", name="Alta"
        )

        # El tipus té una altra tarifa enllaçada: la triada per l'OV ha de
        # guanyar igualment (Option 2a).
        cls.procedure_type.price_rates.set([cls.type_tariff])
        cls.procedure_type.registration_price_rates.set([cls.type_tariff])
        cls.procedure_type.order_types.set([cls.order_type])

        cls.holder = Person.objects.create(
            token="12345678A", name="Anna", surname="Prova"
        )
        cls.other_holder = Person.objects.create(
            token="11111111A", name="Bernat", surname="Prova"
        )

        cls.property = Property.objects.create(
            token="PROP-1", name="Finca 1", is_active=True
        )
        cls.supply_point = SupplyPoint.objects.create(
            token="SP-1", property=cls.property, is_active=True
        )

        cls.property_2 = Property.objects.create(
            token="PROP-2", name="Finca 2", is_active=True
        )
        cls.supply_point_2 = SupplyPoint.objects.create(
            token="SP-2", property=cls.property_2, is_active=True
        )

        cls.property_without_sp = Property.objects.create(
            token="PROP-3", name="Finca 3", is_active=True
        )
        cls.inactive_property = Property.objects.create(
            token="PROP-OFF", name="Finca off", is_active=False
        )

        cls.multi_property = Property.objects.create(
            token="PROP-4", name="Finca 4", is_active=True
        )
        cls.multi_sp_a = SupplyPoint.objects.create(
            token="SP-A", property=cls.multi_property, is_active=True
        )
        cls.multi_sp_b = SupplyPoint.objects.create(
            token="SP-B", property=cls.multi_property, is_active=True
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _post(self, **overrides):
        payload = {
            "holder_dni": "12345678A",
            "property_token": "PROP-1",
            "procedure_type_token": "domestic",
            "tariff_token": "TR-CHOSEN",
            "payment_type_token": "DIRECT_DEBIT",
            "iban": "ES91 2100 0418 4502 0005 1332",
            "iban_holder_name": "Anna Prova",
            "iban_holder_dni": "12345678a",
            "iban_holder_swift": "CAIXESBBXXX",
            "observation": "Alta sol·licitada des de l'OV",
        }
        payload.update(overrides)
        return self.client.post(
            reverse("contract-procedure-ov"), payload, format="json"
        )

    def _created_request(self, response):
        return ContractRequest.objects.get(
            token=response.data["contract_request_token"]
        )

    def test_creates_draft_request_without_creating_contract(self):
        contract_count = Contract.objects.count()

        response = self._post()

        self.assertEqual(response.status_code, 201)
        request_obj = self._created_request(response)
        self.assertEqual(request_obj.person, self.holder)
        self.assertEqual(request_obj.holder, self.holder)
        self.assertEqual(
            request_obj.supply_point_default, self.supply_point
        )
        self.assertEqual(
            list(request_obj.supply_points.all()), [self.supply_point]
        )
        self.assertEqual(request_obj.type, self.procedure_type)
        self.assertEqual(request_obj.status, self.default_status)
        self.assertIsNotNone(request_obj.requested_at)
        self.assertIsNone(request_obj.approved_at)
        self.assertTrue(request_obj.is_active)
        self.assertIsNotNone(request_obj.payment)
        self.assertEqual(Contract.objects.count(), contract_count)

        self.assertEqual(
            response.data["contract_request_token"], request_obj.token
        )
        self.assertEqual(response.data["status"]["token"], "1")
        self.assertEqual(response.data["type"]["token"], "domestic")
        self.assertEqual(response.data["person"]["token"], "12345678A")
        self.assertEqual(response.data["supply_point"]["token"], "SP-1")
        self.assertEqual(
            response.data["payment"]["iban"],
            "ES912100********00051332",
        )

    def test_chosen_tariff_wins_over_procedure_type_tariffs(self):
        response = self._post()

        self.assertEqual(response.status_code, 201)
        request_obj = self._created_request(response)
        contract_price_rates = list(
            request_obj.price_rates.select_related(
                "price_rate", "supply_point"
            )
        )
        self.assertEqual(len(contract_price_rates), 1)
        self.assertEqual(
            contract_price_rates[0].price_rate, self.tariff
        )
        self.assertEqual(
            contract_price_rates[0].supply_point, self.supply_point
        )
        self.assertNotIn(
            self.type_tariff,
            [cpr.price_rate for cpr in contract_price_rates],
        )

    def test_reuses_an_active_contract_price_rate_when_duplicates_exist(self):
        inactive = ContractPriceRate.objects.create(
            supply_point=self.supply_point, price_rate=self.tariff, is_active=False
        )
        active_rates = [
            ContractPriceRate.objects.create(
                supply_point=self.supply_point, price_rate=self.tariff, is_active=True
            )
            for _ in range(2)
        ]
        count = ContractPriceRate.objects.count()

        response = self._post()

        self.assertEqual(response.status_code, 201)
        chosen = self._created_request(response).price_rates.get()
        self.assertIn(chosen, active_rates)
        self.assertTrue(chosen.is_active)
        self.assertEqual(ContractPriceRate.objects.count(), count)
        inactive.refresh_from_db()
        self.assertFalse(inactive.is_active)

    def test_creates_active_contract_price_rate_when_only_inactive_exists(self):
        inactive = ContractPriceRate.objects.create(
            supply_point=self.supply_point, price_rate=self.tariff, is_active=False
        )
        count = ContractPriceRate.objects.count()

        response = self._post()

        self.assertEqual(response.status_code, 201)
        chosen = self._created_request(response).price_rates.get()
        self.assertNotEqual(chosen.pk, inactive.pk)
        self.assertTrue(chosen.is_active)
        self.assertEqual(chosen.supply_point, self.supply_point)
        self.assertEqual(chosen.price_rate, self.tariff)
        self.assertEqual(ContractPriceRate.objects.count(), count + 1)
        inactive.refresh_from_db()
        self.assertFalse(inactive.is_active)

    def test_registration_rates_and_order_types_come_from_type(self):
        response = self._post()

        self.assertEqual(response.status_code, 201)
        request_obj = self._created_request(response)
        self.assertEqual(
            set(request_obj.registration_price_rates.all()),
            set(self.procedure_type.registration_price_rates.all()),
        )
        self.assertEqual(
            set(request_obj.order_types.all()),
            set(self.procedure_type.order_types.all()),
        )

    def test_creates_person_bank_and_general_payment(self):
        response = self._post()

        self.assertEqual(response.status_code, 201)
        request_obj = self._created_request(response)
        general_payment = request_obj.payment
        self.assertEqual(general_payment.type, self.payment_type)
        self.assertTrue(general_payment.is_active)

        person_bank = general_payment.IBAN
        self.assertIsNotNone(person_bank)
        self.assertEqual(person_bank.person, self.holder)
        self.assertEqual(
            person_bank.iban, "ES9121000418450200051332"
        )
        self.assertEqual(person_bank.swift, "CAIXESBBXXX")
        self.assertEqual(person_bank.name, "Anna Prova")
        self.assertEqual(person_bank.dni, "12345678A")

    def test_writes_status_change_log(self):
        response = self._post()

        self.assertEqual(response.status_code, 201)
        request_obj = self._created_request(response)
        log = LogContractRequestStatus.objects.get(object=request_obj)
        self.assertIsNone(log.previous_status)
        self.assertEqual(log.current_status, self.default_status)
        self.assertEqual(log.user, self.user)
        self.assertEqual(
            log.observation, "Alta sol·licitada des de l'OV"
        )

    def test_non_direct_debit_does_not_require_iban(self):
        response = self._post(
            payment_type_token="CASH",
            iban="",
            iban_holder_name="",
            iban_holder_dni="",
            iban_holder_swift="",
        )

        self.assertEqual(response.status_code, 201)
        request_obj = self._created_request(response)
        self.assertEqual(request_obj.payment.type, self.cash_payment_type)
        self.assertIsNone(request_obj.payment.IBAN)
        self.assertEqual(response.data["payment"]["iban"], "")

    def test_duplicate_open_request_returns_409_and_reuses_token(self):
        first = self._post()
        second = self._post()

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(
            second.data["error"], "Contract request already exists"
        )
        self.assertEqual(
            second.data["contract_request_token"],
            first.data["contract_request_token"],
        )
        self.assertEqual(
            ContractRequest.objects.filter(
                person=self.holder,
                supply_point_default=self.supply_point,
            ).count(),
            1,
        )

    def test_cancelled_request_does_not_block(self):
        ContractRequest.objects.create(
            token="CR-CANCELLED",
            person=self.holder,
            holder=self.holder,
            supply_point_default=self.supply_point,
            status=self.cancelled_status,
            is_active=True,
        )

        response = self._post()

        self.assertEqual(response.status_code, 201)

    def test_unknown_person_returns_404(self):
        response = self._post(holder_dni="99999999Z")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Person not found"})

    def test_bank_account_dni_cannot_resolve_a_different_holder(self):
        PersonBank.objects.create(
            person=self.holder, dni="99999999Z", iban="ES9121000418450200051332"
        )
        request_count = ContractRequest.objects.count()

        response = self._post(holder_dni="99999999Z")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Person not found"})
        self.assertEqual(ContractRequest.objects.count(), request_count)

    def test_unknown_or_inactive_property_returns_404(self):
        for property_token in ("PROP-UNKNOWN", "PROP-OFF"):
            with self.subTest(property_token=property_token):
                response = self._post(property_token=property_token)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(
                    response.data, {"error": "Property not found"}
                )

    def test_property_without_supply_point_returns_404(self):
        response = self._post(property_token="PROP-3")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.data, {"error": "Supply point not found"}
        )

    def test_supply_point_of_another_property_returns_404(self):
        response = self._post(
            property_token="PROP-1", supply_point_token="SP-2"
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.data, {"error": "Supply point not found"}
        )

    def test_ambiguous_supply_point_requires_token(self):
        ambiguous = self._post(property_token="PROP-4")
        resolved = self._post(
            property_token="PROP-4", supply_point_token="SP-A"
        )

        self.assertEqual(ambiguous.status_code, 400)
        self.assertEqual(
            ambiguous.data, {"error": "supply_point_token is required"}
        )
        self.assertEqual(resolved.status_code, 201)
        request_obj = self._created_request(resolved)
        self.assertEqual(request_obj.supply_point_default, self.multi_sp_a)

    def test_unknown_or_inactive_procedure_type_returns_404(self):
        for type_token in ("unknown", "industrial"):
            with self.subTest(type_token=type_token):
                response = self._post(
                    procedure_type_token=type_token
                )
                self.assertEqual(response.status_code, 404)
                self.assertEqual(
                    response.data, {"error": "Procedure type not found"}
                )

    def test_unknown_or_inactive_tariff_returns_404(self):
        for tariff_token in ("TR-UNKNOWN", "TR-OFF"):
            with self.subTest(tariff_token=tariff_token):
                response = self._post(tariff_token=tariff_token)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(
                    response.data, {"error": "Tariff not found"}
                )

    def test_unknown_payment_type_returns_404(self):
        response = self._post(payment_type_token="UNKNOWN")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.data, {"error": "Payment type not found"}
        )

    def test_missing_or_blank_fields_return_400(self):
        for field in (
            "holder_dni",
            "property_token",
            "procedure_type_token",
            "tariff_token",
            "payment_type_token",
        ):
            for value in ("", "   "):
                with self.subTest(field=field, value=value):
                    response = self._post(**{field: value})
                    self.assertEqual(response.status_code, 400)

    def test_direct_debit_requires_bank_fields(self):
        response = self._post(
            iban="",
            iban_holder_name="",
            iban_holder_dni="",
            iban_holder_swift="",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            set(response.data["error"].keys()),
            {
                "iban",
                "iban_holder_name",
                "iban_holder_dni",
                "iban_holder_swift",
            },
        )

    def test_requires_authentication(self):
        anonymous = APIClient()

        response = anonymous.post(
            reverse("contract-procedure-ov"),
            {
                "holder_dni": "12345678A",
                "property_token": "PROP-1",
                "procedure_type_token": "domestic",
                "tariff_token": "TR-CHOSEN",
                "payment_type_token": "DIRECT_DEBIT",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_endpoint_uses_dedicated_throttle(self):
        self.assertEqual(
            ContractProcedureOVView.throttle_classes,
            [ContractProcedureThrottle],
        )
        self.assertEqual(ContractProcedureThrottle.rate, "35/min")

    def test_route_does_not_shadow_existing_procedures_endpoints(self):
        match = resolve(reverse("contract-procedure-ov"))
        self.assertIs(match.func.view_class, ContractProcedureOVView)

        # Les rutes de SEPA del mateix prefix continuen resolent-se a la seva
        # vista i no a la nova.
        sepa_match = resolve(
            reverse("upload-sepa-signed-ov", args=["CONTRACT-1"])
        )
        self.assertNotEqual(sepa_match.url_name, "contract-procedure-ov")
