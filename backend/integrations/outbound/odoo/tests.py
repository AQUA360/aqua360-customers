from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import requests
from django.test import TestCase, override_settings

from integrations.models import IntegrationRequestLog
from integrations.outbound.odoo.client import (
    INVOICES_ENDPOINT,
    JSON2_INVOICE_ENDPOINT,
    JSON2_PAYMENT_ENDPOINT,
    OdooClient,
    PROVIDER,
)
from integrations.outbound.odoo.services import push_commitment_deposit_batch
from integrations.outbound.odoo.exceptions import OdooApiError, OdooMappingError
from integrations.outbound.odoo.mappers import (
    is_movement_pushable,
    map_commitment_deposit_cancel_to_odoo,
    map_commitment_deposit_create_to_odoo,
    map_invoice_to_odoo,
    map_payment_movement_to_odoo,
    resolve_partner,
    resolve_partner_vat,
)


def _build_invoice(**overrides):
    invoice = MagicMock()
    invoice.token = "2026Q3-000123"
    invoice.serie_final = "FA2026/000123"
    invoice.issue_date = date(2026, 7, 15)
    invoice.due_date = date(2026, 8, 15)
    invoice.subtotal_final = Decimal("25.00")
    invoice.total_final = Decimal("27.50")
    invoice.customer_token_final = "ABON-004521"
    invoice.customer_final = "Joan Puig Vidal"
    invoice.payer_token_final = None
    invoice.payment_type_token_final = "DIRECT_DEBIT"
    invoice.payment_type_final = "Domiciliació SEPA"
    invoice.parent_invoice_id = None
    invoice.parent_invoice = None
    invoice.company = MagicMock(vat="ES12345678Z")
    invoice.contract = None
    invoice.contract_request = None
    invoice.contract_termination = None

    serie = MagicMock()
    serie.token = "VENT-AGUA"
    serie.name = "Facturació aigua"
    invoice.serie = serie

    product = MagicMock()
    product.token = "CONS-AGUA-B1"
    product.name = "Consum aigua bloc 1"
    product.company = MagicMock()
    product.company.name = "Aigües Exemple"
    product.company.vat = "B12345678"

    tax = MagicMock()
    tax.token = "IVA10"

    line = MagicMock()
    line.id = 1
    line.product = product
    line.product_name = "Consum aigua bloc 1"
    line.name = "Consum aigua bloc 1 (0-10 m³)"
    line.description = None
    line.units = 10.0
    line.price_unit = 0.65
    line.price = 6.50
    line.tax_price = 0.65
    line.total = Decimal("7.15")
    line.tax = tax

    qs = MagicMock()
    qs.exists.return_value = True
    qs.__iter__.return_value = iter([line])
    invoice.line_items.filter.return_value.select_related.return_value = qs

    for key, value in overrides.items():
        setattr(invoice, key, value)
    return invoice


def _build_movement(**overrides):
    movement = MagicMock()
    movement.id = 7
    movement.token = "MOV-0007-000123"
    movement.is_active = True
    movement.is_positive = True
    movement.movement_date = date(2026, 7, 20)
    movement.payment_remittance = None
    movement.payment_type = MagicMock(token="DIRECT_DEBIT", name="Domiciliació SEPA")
    movement.payoff_invoice = None

    invoice = _build_invoice()
    payment = MagicMock()
    payment.amount = Decimal("27.50")
    payment.payment_type_token = "DIRECT_DEBIT"
    payment.payment_type = "Domiciliació SEPA"
    payment.invoice = invoice
    movement.payment = payment

    for key, value in overrides.items():
        setattr(movement, key, value)
    return movement


def _build_commitment_deposit(**overrides):
    deposit = MagicMock()
    deposit.id = 42
    deposit.token = "03000001234"
    deposit.start_date = date(2026, 10, 1)
    deposit.created_at = None
    deposit.updated_at = None

    inv_qs = MagicMock()
    inv_qs.exclude.return_value.exclude.return_value.order_by.return_value.values_list.return_value = [
        "2026Q3-000123",
        "2026Q3-000124",
    ]
    deposit.invoices = inv_qs

    term1 = MagicMock()
    term1.id = 1
    term1.due_date = date(2026, 11, 1)
    term1.amount = Decimal("50.00")
    term2 = MagicMock()
    term2.id = 2
    term2.due_date = date(2026, 12, 1)
    term2.amount = Decimal("50.00")

    terms_qs = MagicMock()
    terms_qs.filter.return_value.exclude.return_value.exclude.return_value.order_by.return_value = [
        term1,
        term2,
    ]
    deposit.payment_commitments = terms_qs

    for key, value in overrides.items():
        setattr(deposit, key, value)
    return deposit


class OdooMappersTest(TestCase):
    def test_map_invoice_to_odoo(self):
        payload = map_invoice_to_odoo(_build_invoice())

        self.assertEqual(payload["aqua_id"], "2026Q3-000123")
        self.assertEqual(payload["move_type"], "out_invoice")
        self.assertEqual(payload["journal_id"]["aqua_id"], "VENT-AGUA")
        self.assertEqual(payload["payment_mode_id"]["id"], "DIRECT_DEBIT")
        self.assertEqual(payload["invoice_line_ids"][0]["tax_ids"], ["IVA10"])
        self.assertEqual(
            payload["invoice_line_ids"][0]["product_id"]["company"],
            {"name": "Aigües Exemple", "vat": "B12345678"},
        )
        self.assertEqual(payload["amount_total"], 27.50)
        self.assertEqual(payload["partner_id"]["aqua_id"], "ABON-004521")
        self.assertEqual(payload["partner_id"]["name"], "Joan Puig Vidal")
        self.assertEqual(payload["partner_id"]["vat"], "ABON-004521")

    def test_map_invoice_refund(self):
        parent = MagicMock(token="2026Q3-000100")
        invoice = _build_invoice(
            parent_invoice_id=1,
            parent_invoice=parent,
        )
        payload = map_invoice_to_odoo(invoice)

        self.assertEqual(payload["move_type"], "out_refund")
        self.assertEqual(payload["reversed_aqua_id"], "2026Q3-000100")

    def test_resolve_partner_vat_is_customer_token(self):
        invoice = _build_invoice(
            company=MagicMock(vat="ES12345678Z"),
            payer_token_final="12345678Z",
        )
        self.assertEqual(resolve_partner_vat(invoice), "ABON-004521")

    def test_resolve_partner_aqua_id_from_contract(self):
        invoice = _build_invoice(contract=MagicMock(token="CTR-100"))
        partner = resolve_partner(invoice)
        self.assertEqual(partner["aqua_id"], "CTR-100")
        self.assertEqual(partner["name"], "Joan Puig Vidal")
        self.assertEqual(partner["vat"], "ABON-004521")

    def test_resolve_partner_aqua_id_from_contract_request(self):
        invoice = _build_invoice(contract_request=MagicMock(token="CTR-200"))
        partner = resolve_partner(invoice)
        self.assertEqual(partner["aqua_id"], "CTR-200")
        self.assertEqual(partner["vat"], "ABON-004521")

    def test_resolve_partner_aqua_id_from_contract_termination(self):
        termination = MagicMock(contract=MagicMock(token="CTR-300"))
        invoice = _build_invoice(contract_termination=termination)
        partner = resolve_partner(invoice)
        self.assertEqual(partner["aqua_id"], "CTR-300")
        self.assertEqual(partner["vat"], "ABON-004521")

    def test_resolve_partner_prefers_contract_over_request_and_termination(self):
        invoice = _build_invoice(
            contract=MagicMock(token="CTR-100"),
            contract_request=MagicMock(token="CTR-200"),
            contract_termination=MagicMock(contract=MagicMock(token="CTR-300")),
        )
        self.assertEqual(resolve_partner(invoice)["aqua_id"], "CTR-100")

    def test_map_invoice_missing_serie_raises(self):
        invoice = _build_invoice()
        invoice.serie = None
        with self.assertRaises(OdooMappingError):
            map_invoice_to_odoo(invoice)

    def test_map_payment_movement_to_odoo(self):
        payload = map_payment_movement_to_odoo(_build_movement())

        self.assertEqual(payload["aqua_id"], "MOV-0007-000123")
        self.assertEqual(payload["payment_type"], "inbound")
        self.assertEqual(payload["reconcile"]["invoice_aqua_id"], "2026Q3-000123")
        self.assertEqual(payload["amount"], 27.50)

    def test_map_commitment_deposit_create_to_odoo(self):
        payload = map_commitment_deposit_create_to_odoo(_build_commitment_deposit())

        self.assertEqual(payload["id_compromis"], "03000001234")
        self.assertEqual(payload["date"], "2026-10-01")
        self.assertEqual(
            payload["aqua_invoice_ids"], ["2026Q3-000123", "2026Q3-000124"]
        )
        self.assertEqual(
            payload["commitment_terms"],
            [
                {"due_date": "2026-11-01", "amount": 50.0},
                {"due_date": "2026-12-01", "amount": 50.0},
            ],
        )

    def test_map_commitment_deposit_cancel_to_odoo(self):
        deposit = _build_commitment_deposit(
            updated_at=MagicMock(date=lambda: date(2026, 10, 15))
        )
        payload = map_commitment_deposit_cancel_to_odoo(deposit)

        self.assertEqual(payload["id_compromis"], "03000001234")
        self.assertEqual(payload["date"], "2026-10-15")

    def test_map_commitment_deposit_create_missing_terms_raises(self):
        deposit = _build_commitment_deposit()
        empty = MagicMock()
        empty.filter.return_value.exclude.return_value.exclude.return_value.order_by.return_value = []
        deposit.payment_commitments = empty
        with self.assertRaises(OdooMappingError):
            map_commitment_deposit_create_to_odoo(deposit)

    def test_map_payment_movement_return_has_negative_amount(self):
        movement = _build_movement(is_positive=False)
        self.assertTrue(is_movement_pushable(movement))

        payload = map_payment_movement_to_odoo(movement)

        self.assertEqual(payload["payment_type"], "inbound")
        self.assertEqual(payload["amount"], -27.50)
        self.assertEqual(payload["reconcile"]["invoice_aqua_id"], "2026Q3-000123")
        self.assertEqual(payload["memo"], "Cobrament rebut FA2026/000123")

    def test_map_payment_movement_without_invoice(self):
        movement = _build_movement()
        movement.payoff_invoice = None
        movement.payment.invoice = None
        movement.payment.customer_token_final = "ABON-004521"
        movement.payment.customer_final = "Joan Puig Vidal"
        movement.payment.payer_token_final = "12345678Z"
        movement.payment.contract = None

        payload = map_payment_movement_to_odoo(movement)

        self.assertEqual(payload["reconcile"]["invoice_aqua_id"], "")
        self.assertEqual(payload["partner_id"]["aqua_id"], "ABON-004521")
        self.assertEqual(payload["partner_id"]["name"], "Joan Puig Vidal")
        self.assertEqual(payload["partner_id"]["vat"], "12345678Z")
        self.assertEqual(payload["amount"], 27.50)
        self.assertEqual(payload["memo"], "Cobrament rebut")

    def test_is_movement_pushable_false_when_sign_unknown(self):
        movement = _build_movement(is_positive=None)
        self.assertFalse(is_movement_pushable(movement))

    def test_map_payment_movement_not_pushable_raises(self):
        movement = _build_movement(is_active=False)
        with self.assertRaises(OdooMappingError):
            map_payment_movement_to_odoo(movement)


@override_settings(
    ODOO_BASE_URL="https://odoo.example.com/aqua360/v1",
    ODOO_API_KEY="test-key",
    ODOO_TIMEOUT=10,
    ODOO_TRANSPORT="fastapi",
)
class OdooClientTest(TestCase):
    @patch("integrations.outbound.odoo.client.requests.request")
    def test_push_invoice_success(self, mock_request):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 42, "aqua_id": "2026Q3-000123"}
        mock_request.return_value = mock_response

        payload = {"aqua_id": "2026Q3-000123", "move_type": "out_invoice"}
        client = OdooClient()
        result = client.push_invoice(payload)

        self.assertEqual(result["id"], 42)
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        self.assertEqual(call_args.args[0], "POST")
        call_kwargs = call_args.kwargs
        self.assertEqual(
            call_kwargs["headers"]["Aqua360-Api-Key"],
            "test-key",
        )

        log = IntegrationRequestLog.objects.get()
        self.assertEqual(log.provider, PROVIDER)
        self.assertEqual(log.endpoint, INVOICES_ENDPOINT)
        self.assertTrue(log.success)
        self.assertEqual(log.object_type, "invoice")

    @patch("integrations.outbound.odoo.client.requests.request")
    def test_push_invoice_http_error(self, mock_request):
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 422
        mock_response.text = "Totals no quadren"
        mock_response.json.return_value = {"detail": "Totals no quadren"}
        mock_request.return_value = mock_response

        client = OdooClient()
        with self.assertRaises(OdooApiError):
            client.push_invoice({"aqua_id": "X"})

        log = IntegrationRequestLog.objects.get()
        self.assertFalse(log.success)
        self.assertEqual(log.status_code, 422)

    @patch("integrations.outbound.odoo.client.requests.request")
    def test_push_invoice_connection_error(self, mock_request):
        mock_request.side_effect = requests.RequestException("timeout")

        client = OdooClient()
        with self.assertRaises(OdooApiError):
            client.push_invoice({"aqua_id": "X"})

        log = IntegrationRequestLog.objects.get()
        self.assertFalse(log.success)

    @patch("integrations.outbound.odoo.client.requests.request")
    def test_push_invoice_batch_accepted(self, mock_request):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 202
        mock_response.json.return_value = {
            "batch_id": "INV-20261029-abc",
            "status": "pending",
            "items": 2,
            "received_at": "2026-10-21T13:04:00Z",
        }
        mock_request.return_value = mock_response

        client = OdooClient()
        result = client.push_batch(
            "/batch/invoices",
            "INV-20261029-abc",
            [{"aqua_id": "A"}, {"aqua_id": "B"}],
            object_type="send_batch_invoices",
        )

        self.assertEqual(result["status_code"], 202)
        self.assertEqual(result["payload"]["status"], "pending")
        call_args = mock_request.call_args
        self.assertEqual(call_args.args[0], "POST")
        call_kwargs = call_args.kwargs
        self.assertEqual(
            call_kwargs["json"],
            {"batch_id": "INV-20261029-abc", "items": [{"aqua_id": "A"}, {"aqua_id": "B"}]},
        )
        log = IntegrationRequestLog.objects.get()
        self.assertEqual(log.endpoint, "/batch/invoices")
        self.assertTrue(log.success)


@override_settings(
    ODOO_BASE_URL="https://aquaoleiros-t1.odoo.com",
    ODOO_API_KEY="saas-key",
    ODOO_TIMEOUT=10,
    ODOO_TRANSPORT="json2",
)
class OdooJson2ClientTest(TestCase):
    def test_blank_or_default_transport_is_fastapi(self):
        self.assertFalse(OdooClient(transport="").is_json2)
        self.assertFalse(OdooClient(transport="fastapi").is_json2)

    def test_unknown_transport_raises(self):
        with self.assertRaises(OdooApiError):
            OdooClient(transport="xmlrpc")

    @patch("integrations.outbound.odoo.client.requests.request")
    def test_push_invoice_wraps_contract_json(self, mock_request):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = [42]
        mock_request.return_value = mock_response

        payload = {"aqua_id": "000006", "move_type": "out_invoice", "name": "FA1"}
        result = OdooClient().push_invoice(payload)

        self.assertEqual(result, [42])
        call_args = mock_request.call_args
        self.assertEqual(call_args.args[0], "POST")
        self.assertEqual(
            call_args.args[1],
            f"https://aquaoleiros-t1.odoo.com{JSON2_INVOICE_ENDPOINT}",
        )
        headers = call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer saas-key")
        self.assertNotIn("Aqua360-Api-Key", headers)
        self.assertEqual(
            call_args.kwargs["json"],
            {
                "vals_list": [
                    {
                        "x_aqua_id": "000006",
                        "x_aqua_json": payload,
                    }
                ]
            },
        )
        log = IntegrationRequestLog.objects.get()
        self.assertEqual(log.endpoint, JSON2_INVOICE_ENDPOINT)
        self.assertEqual(log.object_id, "000006")
        self.assertTrue(log.success)

    @patch("integrations.outbound.odoo.client.requests.request")
    def test_push_payment_uses_payment_model(self, mock_request):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = [7]
        mock_request.return_value = mock_response

        OdooClient().push_payment({"aqua_id": "MOV-1", "amount": 10})

        self.assertEqual(
            mock_request.call_args.args[1],
            f"https://aquaoleiros-t1.odoo.com{JSON2_PAYMENT_ENDPOINT}",
        )

    @patch("integrations.outbound.odoo.client.requests.request")
    def test_push_batch_one_call_per_item_and_keeps_going(self, mock_request):
        ok = MagicMock()
        ok.ok = True
        ok.status_code = 200
        ok.json.return_value = [11]
        ok.text = "[11]"
        bad = MagicMock()
        bad.ok = False
        bad.status_code = 400
        bad.text = "falta diari"
        bad.json.return_value = {"message": "falta diari"}
        mock_request.side_effect = [ok, bad]

        result = OdooClient().push_batch(
            "/batch/invoices",
            "FACT-1",
            [{"aqua_id": "A", "name": "1"}, {"aqua_id": "B", "name": "2"}],
            object_type="send_batch_invoices",
        )

        self.assertEqual(mock_request.call_count, 2)
        self.assertEqual(result["status_code"], 200)
        payload = result["payload"]
        self.assertEqual(payload["batch_id"], "FACT-1")
        self.assertEqual(payload["status"], "done")
        self.assertEqual(payload["summary"]["total"], 2)
        self.assertEqual(payload["summary"]["ok"], 1)
        self.assertEqual(payload["summary"]["error"], 1)
        self.assertEqual(payload["results"][0]["status"], "ok")
        self.assertEqual(payload["results"][0]["odoo_id"], 11)
        self.assertEqual(payload["results"][1]["status"], "error")
        self.assertIn("falta diari", payload["results"][1]["message"])
        self.assertEqual(IntegrationRequestLog.objects.count(), 2)

    def test_push_batch_commitments_rejected(self):
        with self.assertRaises(OdooApiError) as ctx:
            OdooClient().push_batch(
                "/batch/commitment/create",
                "COM-1",
                [{"aqua_id": "C"}],
                object_type="send_batch_commitment_create",
            )
        self.assertIn("compromisos", str(ctx.exception))

    def test_get_batch_status_rejected(self):
        with self.assertRaises(OdooApiError):
            OdooClient().get_batch_status("FACT-1")

    def test_push_commitment_deposit_batch_rejected(self):
        with self.assertRaises(OdooApiError) as ctx:
            push_commitment_deposit_batch([1])
        self.assertIn("compromisos", str(ctx.exception))
