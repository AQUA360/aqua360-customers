from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import requests
from django.test import TestCase, override_settings

from integrations.models import IntegrationRequestLog
from integrations.outbound.odoo.client import INVOICES_ENDPOINT, OdooClient, PROVIDER
from integrations.outbound.odoo.exceptions import OdooApiError, OdooMappingError
from integrations.outbound.odoo.mappers import (
    is_movement_pushable,
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


class OdooMappersTest(TestCase):
    def test_map_invoice_to_odoo(self):
        payload = map_invoice_to_odoo(_build_invoice())

        self.assertEqual(payload["aqua_id"], "2026Q3-000123")
        self.assertEqual(payload["move_type"], "out_invoice")
        self.assertEqual(payload["journal_id"]["aqua_id"], "VENT-AGUA")
        self.assertEqual(payload["payment_mode_id"]["id"], "DIRECT_DEBIT")
        self.assertEqual(payload["invoice_line_ids"][0]["tax_ids"], ["IVA10"])
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
)
class OdooClientTest(TestCase):
    @patch("integrations.outbound.odoo.client.requests.post")
    def test_push_invoice_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 42, "aqua_id": "2026Q3-000123"}
        mock_post.return_value = mock_response

        payload = {"aqua_id": "2026Q3-000123", "move_type": "out_invoice"}
        client = OdooClient()
        result = client.push_invoice(payload)

        self.assertEqual(result["id"], 42)
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(
            call_kwargs["headers"]["Aqua360-Api-Key"],
            "test-key",
        )

        log = IntegrationRequestLog.objects.get()
        self.assertEqual(log.provider, PROVIDER)
        self.assertEqual(log.endpoint, INVOICES_ENDPOINT)
        self.assertTrue(log.success)
        self.assertEqual(log.object_type, "invoice")

    @patch("integrations.outbound.odoo.client.requests.post")
    def test_push_invoice_http_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 422
        mock_response.text = "Totals no quadren"
        mock_response.json.return_value = {"detail": "Totals no quadren"}
        mock_post.return_value = mock_response

        client = OdooClient()
        with self.assertRaises(OdooApiError):
            client.push_invoice({"aqua_id": "X"})

        log = IntegrationRequestLog.objects.get()
        self.assertFalse(log.success)
        self.assertEqual(log.status_code, 422)

    @patch("integrations.outbound.odoo.client.requests.post")
    def test_push_invoice_connection_error(self, mock_post):
        mock_post.side_effect = requests.RequestException("timeout")

        client = OdooClient()
        with self.assertRaises(OdooApiError):
            client.push_invoice({"aqua_id": "X"})

        log = IntegrationRequestLog.objects.get()
        self.assertFalse(log.success)
