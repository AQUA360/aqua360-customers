import datetime
import hashlib
import hmac
import io
import json
import time
from contextlib import contextmanager
from unittest import mock

import requests
from django.core.management import CommandError, call_command
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from billing.models import Billing, Invoice, InvoiceLineItem, InvoiceType
from contract.models import (
    BailStatus,
    Contract,
    ContractRequest,
    ContractStatus,
    ContractTerminationRequest,
    ContractTerminationStatus,
)
from contract.utils.contract_termination_service import cancel_contract_termination, mark_contract_terminated
from coredata.models import ConfigProject, Person
from integrations.models import IntegrationRequestLog, WebhookEvent
from integrations.outbound.webhooks import events
from integrations.outbound.webhooks.client import build_headers, serialize_payload, sign
from integrations.outbound.webhooks.dispatcher import emit
from integrations.outbound.webhooks.tasks import send_pending_webhooks
from service.models import SupplyPoint

URL = "https://receiver.example/hooks"
SECRET = "test-secret"
ACTIVE = override_settings(WEBHOOKS_ENABLED=True, WEBHOOKS_URL=URL, WEBHOOKS_SECRET=SECRET, WEBHOOKS_SEND_INTERVAL=0)


def http_response(status_code, text="ok"):
    response = mock.Mock()
    response.status_code = status_code
    return response


class DispatcherTest(TestCase):
    @override_settings(WEBHOOKS_ENABLED=False)
    def test_disabled_saves_nothing_and_does_not_build_data(self):
        build = mock.Mock(return_value={})
        self.assertIsNone(emit("contract.created", "contract", 1, build))
        build.assert_not_called()
        self.assertFalse(WebhookEvent.objects.exists())

    @override_settings(WEBHOOKS_ENABLED=True, WEBHOOKS_URL="")
    def test_enabled_without_url_saves_as_disabled(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            event = emit("contract.created", "contract", 1, lambda: {"a": 1})
        self.assertEqual(event.status, WebhookEvent.STATUS_DISABLED)
        self.assertEqual(callbacks, [])

    @override_settings(WEBHOOKS_ENABLED=True, WEBHOOKS_URL=URL, WEBHOOKS_SECRET="")
    def test_without_secret_is_never_sent_unsigned(self):
        event = emit("contract.created", "contract", 1, lambda: {})
        self.assertEqual(event.status, WebhookEvent.STATUS_DISABLED)

    @ACTIVE
    @override_settings(INSTANCE_UID="instancia-test")
    def test_envelope_and_send_scheduled_on_commit(self):
        with mock.patch("integrations.outbound.webhooks.dispatcher.schedule_send") as schedule:
            with self.captureOnCommitCallbacks(execute=True):
                event = emit("contract.created", "contract", 7, lambda: {"a": 1})
            schedule.assert_called_once()
        payload = event.payload
        self.assertEqual(event.status, WebhookEvent.STATUS_PENDING)
        self.assertEqual(payload["event_id"], str(event.event_id))
        self.assertEqual(payload["event_type"], "contract.created")
        self.assertEqual(payload["version"], "1.0")
        self.assertEqual(payload["source"], {"system": "aqua360-customers", "instance": "instancia-test"})
        self.assertEqual(payload["data"], {"a": 1})
        self.assertEqual(event.object_id, "7")

    @ACTIVE
    def test_rollback_discards_event(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                emit("contract.created", "contract", 1, lambda: {})
                raise RuntimeError("l'acció de negoci falla")
        self.assertFalse(WebhookEvent.objects.exists())

    @ACTIVE
    def test_same_dedupe_key_is_saved_once(self):
        self.assertIsNotNone(emit("invoice.issued", "invoice", 1, lambda: {}, dedupe_key="invoice.issued:1"))
        self.assertIsNone(emit("invoice.issued", "invoice", 1, lambda: {}, dedupe_key="invoice.issued:1"))
        self.assertEqual(WebhookEvent.objects.count(), 1)

    @ACTIVE
    def test_error_building_data_does_not_break_business_transaction(self):
        def broken():
            raise ValueError("dades incompletes")

        with transaction.atomic():
            self.assertIsNone(emit("contract.created", "contract", 1, broken))
            # La transacció continua utilitzable
            person = Person.objects.create(name="Continua")
        self.assertTrue(Person.objects.filter(pk=person.pk).exists())
        self.assertFalse(WebhookEvent.objects.exists())


class ClientTest(TestCase):
    def test_signature_is_hmac_of_timestamp_and_body(self):
        body = serialize_payload({"b": 2, "a": "à"})
        expected = hmac.new(SECRET.encode(), b"1700000000." + body, hashlib.sha256).hexdigest()
        self.assertEqual(sign(SECRET, "1700000000", body), f"sha256={expected}")

    def test_headers_without_secret_have_no_signature(self):
        headers = build_headers("invoice.issued", "id-1", "1700000000", b"{}", "")
        self.assertEqual(headers["X-Aqua360-Event"], "invoice.issued")
        self.assertEqual(headers["X-Aqua360-Event-Id"], "id-1")
        self.assertNotIn("X-Aqua360-Signature", headers)


@ACTIVE
class SendTest(TestCase):
    def _pending(self, **kwargs):
        with mock.patch("integrations.outbound.webhooks.dispatcher.schedule_send"):
            event = emit("contract.created", "contract", 1, lambda: {"x": 1})
        if kwargs:
            WebhookEvent.objects.filter(pk=event.pk).update(**kwargs)
        event.refresh_from_db()
        return event

    @mock.patch("integrations.outbound.webhooks.client._NoRedirectSession.post")
    def test_2xx_marks_sent_and_logs(self, post):
        post.return_value = http_response(204, "")
        event = self._pending()

        result = send_pending_webhooks()

        event.refresh_from_db()
        self.assertEqual(result["sent"], 1)
        self.assertEqual(event.status, WebhookEvent.STATUS_SENT)
        self.assertIsNotNone(event.sent_at)
        _, kwargs = post.call_args
        self.assertEqual(json.loads(kwargs["data"]), event.payload)
        headers = kwargs["headers"]
        self.assertEqual(headers["X-Aqua360-Signature"], sign(SECRET, headers["X-Aqua360-Timestamp"], kwargs["data"]))
        log = IntegrationRequestLog.objects.get(provider="webhooks")
        self.assertTrue(log.success)
        self.assertEqual(log.object_id, str(event.event_id))

    @mock.patch("integrations.outbound.webhooks.client._NoRedirectSession.post")
    def test_5xx_is_retried_later(self, post):
        post.return_value = http_response(503)
        event = self._pending()

        send_pending_webhooks()

        event.refresh_from_db()
        self.assertEqual(event.status, WebhookEvent.STATUS_PENDING)
        self.assertEqual(event.attempts, 1)
        self.assertGreater(event.next_attempt_at, timezone.now() + datetime.timedelta(seconds=30))
        # No es torna a enviar fins que toqui
        send_pending_webhooks()
        self.assertEqual(post.call_count, 1)

    @mock.patch("integrations.outbound.webhooks.client._NoRedirectSession.post")
    def test_network_error_is_retried(self, post):
        post.side_effect = requests.ConnectionError("no hi ha xarxa")
        event = self._pending()

        send_pending_webhooks()

        event.refresh_from_db()
        self.assertEqual(event.status, WebhookEvent.STATUS_PENDING)
        self.assertIn("ConnectionError", event.last_error)

    @mock.patch("integrations.outbound.webhooks.client._NoRedirectSession.post")
    def test_redirect_is_not_a_delivery(self, post):
        post.return_value = http_response(302)
        event = self._pending()

        send_pending_webhooks()

        event.refresh_from_db()
        self.assertEqual(event.status, WebhookEvent.STATUS_FAILED)
        self.assertFalse(post.call_args.kwargs["allow_redirects"])

    @override_settings(WEBHOOKS_URL="https://user:pwd@receiver.example/hooks/tok-path?token=abc#x")
    @mock.patch("integrations.outbound.webhooks.client._NoRedirectSession.post")
    def test_logs_do_not_keep_url_credentials(self, post):
        post.side_effect = requests.ConnectionError("https://user:pwd@receiver.example/hooks?token=abc")
        event = self._pending()

        send_pending_webhooks()

        event.refresh_from_db()
        log = IntegrationRequestLog.objects.get(provider="webhooks")
        self.assertEqual(log.endpoint, "https://receiver.example")
        for text in (log.error_message, event.last_error):
            self.assertNotIn("token", text)
            self.assertNotIn("pwd", text)

    @mock.patch("integrations.outbound.webhooks.client._NoRedirectSession.post")
    def test_log_failure_keeps_delivery_result(self, post):
        post.return_value = http_response(200)
        event = self._pending()

        with mock.patch.object(IntegrationRequestLog.objects, "create", side_effect=ValueError("log")):
            send_pending_webhooks()

        event.refresh_from_db()
        self.assertEqual(event.status, WebhookEvent.STATUS_SENT)

    @mock.patch("integrations.outbound.webhooks.client._NoRedirectSession.post")
    def test_4xx_fails_without_retry(self, post):
        post.return_value = http_response(400, "bad")
        event = self._pending()

        send_pending_webhooks()

        event.refresh_from_db()
        self.assertEqual(event.status, WebhookEvent.STATUS_FAILED)
        self.assertEqual(event.last_status_code, 400)

    @mock.patch("integrations.outbound.webhooks.client._NoRedirectSession.post")
    def test_exhausted_retries_fail(self, post):
        post.return_value = http_response(500)
        event = self._pending(attempts=7)

        send_pending_webhooks()

        event.refresh_from_db()
        self.assertEqual(event.status, WebhookEvent.STATUS_FAILED)

    @mock.patch("integrations.outbound.webhooks.client._NoRedirectSession.post")
    def test_resend_command_requeues_failed(self, post):
        post.return_value = http_response(200)
        event = self._pending(status=WebhookEvent.STATUS_FAILED, attempts=3)

        with mock.patch("integrations.management.commands.resend_webhooks.schedule_send") as schedule:
            call_command("resend_webhooks", stdout=io.StringIO())
            schedule.assert_called_once()

        event.refresh_from_db()
        self.assertEqual(event.status, WebhookEvent.STATUS_PENDING)
        self.assertEqual(event.attempts, 0)

    @mock.patch("integrations.outbound.webhooks.client._NoRedirectSession.post")
    def test_send_test_webhook_command(self, post):
        post.return_value = http_response(200)
        out = io.StringIO()
        call_command("send_test_webhook", stdout=out)
        self.assertIn("Entregat", out.getvalue())
        self.assertEqual(WebhookEvent.objects.get().event_type, "webhook.test")

    @mock.patch("integrations.outbound.webhooks.client._NoRedirectSession.post")
    def test_only_one_sender_at_a_time(self, post):
        self._pending()

        @contextmanager
        def busy():
            yield False

        with mock.patch("integrations.outbound.webhooks.tasks.single_sender", busy):
            self.assertEqual(send_pending_webhooks(), {"status": "busy"})
        post.assert_not_called()

    @mock.patch("integrations.outbound.webhooks.client._NoRedirectSession.post")
    def test_send_test_webhook_fails_with_error_code(self, post):
        post.return_value = http_response(401)
        with self.assertRaises(CommandError):
            call_command("send_test_webhook", stdout=io.StringIO())

    def test_send_test_webhook_busy_sender_is_an_error(self):
        @contextmanager
        def busy():
            yield False

        with mock.patch("integrations.management.commands.send_test_webhook.single_sender", busy), \
                mock.patch("integrations.management.commands.send_test_webhook.schedule_send") as schedule:
            with self.assertRaises(CommandError):
                call_command("send_test_webhook", stdout=io.StringIO())
            schedule.assert_called_once()

    @mock.patch("integrations.outbound.webhooks.client._NoRedirectSession.post")
    def test_response_body_is_never_read(self, post):
        for status_code in (200, 400):
            post.return_value = http_response(status_code)
            self._pending()

            send_pending_webhooks()

            self.assertFalse(post.return_value.raw.method_calls)
            self.assertFalse(post.return_value.iter_content.called)
            post.return_value.close.assert_called_once()

    def test_slow_redirect_body_does_not_hold_the_sender(self):
        """Servidor real que respon 302 amb Location i envia el cos molt a poc a poc."""
        import socket
        import threading

        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        stop = threading.Event()

        def serve():
            conn, _ = listener.accept()
            conn.recv(65536)
            conn.sendall(b"HTTP/1.1 302 Found\r\nLocation: /altre\r\nContent-Length: 1000\r\n\r\n")
            while not stop.wait(0.5):
                try:
                    conn.sendall(b"x")
                except OSError:
                    break
            conn.close()

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        try:
            event = self._pending()
            with override_settings(WEBHOOKS_URL=f"http://127.0.0.1:{port}/hook"):
                started = time.monotonic()
                send_pending_webhooks()
                elapsed = time.monotonic() - started
        finally:
            stop.set()
            listener.close()
        event.refresh_from_db()
        self.assertEqual(event.status, WebhookEvent.STATUS_FAILED)
        self.assertEqual(event.last_status_code, 302)
        self.assertLess(elapsed, 3)

    @override_settings(WEBHOOKS_URL="")
    def test_task_skips_without_url(self):
        self.assertEqual(send_pending_webhooks(), {"status": "skipped"})


@ACTIVE
@mock.patch("integrations.outbound.webhooks.dispatcher.schedule_send")
class ContractEventsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ("contract_active_token", "ACTIVE"),
            ("contract_terminated_status", "TERMINATED"),
            ("contract_termination_cancelled_token", "CT_CANCELLED"),
            ("order_status_completed_token", "OS_COMPLETED"),
            ("contract_termination_pending_token", "CT_PENDING"),
            ("bail_status_pending_token", "BAIL_PENDING"),
            ("bail_status_unreturned_token", "BAIL_UNRETURNED"),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={"value": value})
        cls.active, _ = ContractStatus.objects.get_or_create(token="ACTIVE", defaults={"name": "Actiu"})
        cls.terminated, _ = ContractStatus.objects.get_or_create(token="TERMINATED", defaults={"name": "Baixa"})
        cls.ct_pending, _ = ContractTerminationStatus.objects.get_or_create(token="CT_PENDING", defaults={"name": "Pendent"})
        ContractTerminationStatus.objects.get_or_create(token="CT_CANCELLED", defaults={"name": "Anul·lada"})
        BailStatus.objects.get_or_create(token="BAIL_UNRETURNED", defaults={"name": "No retornada"})
        cls.holder = Person.objects.create(name="Titular", surname="Prova", token="00000000T")

    def _contract(self, token, **kwargs):
        supply_point = SupplyPoint.objects.create(token=f"SP-{token}")
        return Contract.objects.create(
            token=token, status=self.active, holder=self.holder, supply_point_default=supply_point, **kwargs
        )

    def test_contract_created_payload(self, _schedule):
        old = self._contract("OLD-1")
        termination = ContractTerminationRequest.objects.create(contract=old, status=self.ct_pending, token="B-1")
        contract_request = ContractRequest.objects.create(token="CR-1", is_change_of_name=True)
        contract_request.contract_termination_requests.add(termination)
        contract = self._contract("NEW-1", contract_request=contract_request, registration_date=datetime.date(2026, 11, 2))

        event = events.emit_contract_created(contract)
        # Un contracte només s'avisa una vegada
        self.assertIsNone(events.emit_contract_created(contract))

        data = event.payload["data"]
        self.assertEqual(data["contract"], {"id": contract.id, "code": "NEW-1", "registration_date": "2026-11-02"})
        self.assertEqual(data["contract_request"]["code"], "CR-1")
        self.assertTrue(data["contract_request"]["is_change_of_name"])
        self.assertEqual(data["contract_request"]["previous_contract"], {"id": old.id, "code": "OLD-1"})
        self.assertEqual(data["holder"], {"id": self.holder.id, "name": "Titular Prova", "tax_id": "00000000T"})
        self.assertEqual(data["supply_point"]["code"], "SP-NEW-1")

    def test_contract_created_without_registration_date_uses_creation_day(self, _schedule):
        contract = self._contract("NEW-2")
        event = events.emit_contract_created(contract)
        self.assertEqual(
            event.payload["data"]["contract"]["registration_date"], timezone.localdate(contract.created_at).isoformat()
        )
        self.assertIsNone(event.payload["data"]["contract_request"])

    def test_termination_emits_once_and_fills_date(self, _schedule):
        contract = self._contract("C-2")
        termination = ContractTerminationRequest.objects.create(contract=contract, status=self.ct_pending, token="B-2")

        self.assertTrue(mark_contract_terminated(contract, termination))
        # Segon camí (p. ex. en completar les ordres): ja era de baixa, no es repeteix
        self.assertFalse(mark_contract_terminated(contract, termination))

        contract.refresh_from_db()
        self.assertEqual(contract.status, self.terminated)
        self.assertEqual(contract.termination_date, datetime.date.today())
        event = WebhookEvent.objects.get(event_type="contract_termination.confirmed")
        data = event.payload["data"]
        self.assertEqual(data["contract"]["termination_date"], datetime.date.today().isoformat())
        self.assertEqual(data["termination_request"]["code"], "B-2")
        self.assertFalse(data["termination_request"]["is_change_of_name"])
        self.assertEqual(data["holder"]["tax_id"], "00000000T")

    def test_repeated_termination_keeps_notified_date(self, _schedule):
        contract = self._contract("C-5")
        mark_contract_terminated(contract, None, datetime.date(2026, 11, 18))
        mark_contract_terminated(contract, None, datetime.date(2026, 11, 19))
        contract.refresh_from_db()
        self.assertEqual(contract.termination_date, datetime.date(2026, 11, 18))
        self.assertEqual(WebhookEvent.objects.filter(event_type="contract_termination.confirmed").count(), 1)

    def test_termination_keeps_existing_date(self, _schedule):
        contract = self._contract("C-3", termination_date=datetime.date(2026, 10, 1))
        mark_contract_terminated(contract, None)
        contract.refresh_from_db()
        self.assertEqual(contract.termination_date, datetime.date(2026, 10, 1))

    def test_cancel_emits_only_if_contract_was_terminated(self, _schedule):
        contract = self._contract("C-4")
        termination = ContractTerminationRequest.objects.create(contract=contract, status=self.ct_pending, token="B-4")

        cancel_contract_termination(termination, None)
        self.assertFalse(WebhookEvent.objects.filter(event_type="contract_termination.cancelled").exists())

        mark_contract_terminated(contract, termination)
        cancel_contract_termination(termination, None)
        event = WebhookEvent.objects.get(event_type="contract_termination.cancelled")
        self.assertEqual(event.payload["data"]["contract"], {"id": contract.id, "code": "C-4"})


@ACTIVE
@mock.patch("integrations.outbound.webhooks.dispatcher.schedule_send")
class InvoiceEventsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        ConfigProject.objects.update_or_create(token="invoice_type_budget_token", defaults={"value": "P"})
        ConfigProject.objects.update_or_create(token="direct_debit_token", defaults={"value": "DD"})
        ConfigProject.objects.update_or_create(token="contract_terminated_status", defaults={"value": "TERMINATED"})
        ConfigProject.objects.update_or_create(token="invoice_status_cancelled_token", defaults={"value": "CANCELLED"})
        ConfigProject.objects.update_or_create(token="payment_status_paid_token", defaults={"value": "PAID"})
        cls.invoice_type, _ = InvoiceType.objects.get_or_create(token="F", defaults={"name": "Factura"})
        cls.budget_type, _ = InvoiceType.objects.get_or_create(token="P", defaults={"name": "Pressupost"})
        cls.contract = Contract.objects.create(token="C-INV")

    def _invoice(self, number, **kwargs):
        invoice = Invoice.objects.create(
            serie_final=number, serie_token_final="FC", type=self.invoice_type, contract=self.contract,
            issue_date=datetime.date(2026, 11, 18), payment_type_token_final="DD", **kwargs
        )
        InvoiceLineItem.objects.create(invoice=invoice, price=100, tax_percent=10, tax_price=10)
        InvoiceLineItem.objects.create(invoice=invoice, price=50, tax_percent=21, tax_price=10.5)
        return invoice

    def test_invoice_issued_payload(self, _schedule):
        original = self._invoice("FC/1")
        invoice = self._invoice("FC/2", refactored_token="tok-original")
        Invoice.objects.filter(pk=original.pk).update(token="tok-original")

        event = events.emit_invoice_issued(invoice)

        data = event.payload["data"]
        self.assertEqual(data["number"], "FC/2")
        self.assertTrue(data["is_rectifying"])
        self.assertEqual(data["corrects"], {"id": original.id, "number": "FC/1"})
        self.assertEqual(data["contract"], {"id": self.contract.id, "code": "C-INV"})
        self.assertTrue(data["direct_debit"])
        self.assertEqual(data["amounts"]["subtotal"], "150.00")
        self.assertEqual(data["amounts"]["total"], "170.50")
        self.assertEqual(
            data["amounts"]["taxes"],
            [{"rate": "10.00", "base": "100.00", "amount": "10.00"}, {"rate": "21.00", "base": "50.00", "amount": "10.50"}],
        )

    def test_budget_is_not_sent(self, _schedule):
        budget = self._invoice("P/1")
        budget.type = self.budget_type
        self.assertIsNone(events.emit_invoice_issued(budget))
        self.assertFalse(WebhookEvent.objects.exists())

    @override_settings(WEBHOOKS_BILLING_CHUNK_SIZE=2)
    def test_billing_issued_in_chunks(self, schedule):
        billing = Billing.objects.create(name="Facturació de prova")
        invoices = [self._invoice(f"FC/{n}") for n in range(5)]
        budget = self._invoice("P/9")
        Invoice.objects.filter(pk=budget.pk).update(type=self.budget_type)
        ids = [invoice.id for invoice in invoices] + [budget.id]

        with self.captureOnCommitCallbacks(execute=True):
            created = events.emit_billing_issued(billing, ids)

        self.assertEqual(len(created), 3)
        schedule.assert_called_once()
        parts = [event.payload["data"] for event in created]
        self.assertEqual([part["part"] for part in parts], [1, 2, 3])
        self.assertTrue(all(part["parts"] == 3 for part in parts))
        sent_ids = [invoice["id"] for part in parts for invoice in part["invoices"]]
        self.assertEqual(sent_ids, [invoice.id for invoice in invoices])
        # Tornar a processar la mateixa facturació no repeteix els avisos
        self.assertEqual(events.emit_billing_issued(billing, ids), [])
        self.assertEqual(WebhookEvent.objects.count(), 3)


@ACTIVE
@mock.patch("integrations.outbound.webhooks.dispatcher.schedule_send")
class InvoiceStatusScanTest(TestCase):
    """Avisos d'estat de pagament: la tasca compara les factures amb la foto."""

    @classmethod
    def setUpTestData(cls):
        from billing.models import InvoiceStatus, PaymentStatus, RejectMotive

        for token, value in (
            ("invoice_status_paid_token", "I_PAID"),
            ("invoice_status_expired_token", "I_EXPIRED"),
            ("invoice_status_cancelled_token", "I_CANCELLED"),
            ("invoice_status_dropped_token", "I_DROPPED"),
            ("payment_status_paid_token", "P_PAID"),
            ("payment_status_returned_token", "P_RETURNED"),
            ("invoice_type_budget_token", "P"),
            ("direct_debit_token", "DD"),
            ("contract_terminated_status", "TERMINATED"),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={"value": value})
        cls.confirmed = InvoiceStatus.objects.create(token="I_CONFIRMED", name="Confirmada")
        cls.paid = InvoiceStatus.objects.create(token="I_PAID", name="Pagada")
        cls.expired = InvoiceStatus.objects.create(token="I_EXPIRED", name="Vençuda")
        cls.cancelled = InvoiceStatus.objects.create(token="I_CANCELLED", name="Abonada")
        cls.dropped = InvoiceStatus.objects.create(token="I_DROPPED", name="Anul·lada")
        cls.payment_pending = PaymentStatus.objects.create(token="P_PENDING", name="Pendent")
        cls.payment_paid = PaymentStatus.objects.create(token="P_PAID", name="Pagat")
        cls.payment_returned = PaymentStatus.objects.create(token="P_RETURNED", name="Retornat")
        cls.reject = RejectMotive.objects.create(token="AM04", name="Fons insuficients")
        cls.invoice_type, _ = InvoiceType.objects.get_or_create(token="F", defaults={"name": "Factura"})
        cls.budget_type, _ = InvoiceType.objects.get_or_create(token="P", defaults={"name": "Pressupost"})
        cls.holder = Person.objects.create(name="Titular", surname="Prova", token="00000000T")
        cls.contract = Contract.objects.create(token="C-STATUS", holder=cls.holder)

    def _invoice(self, number, status=None, **kwargs):
        """Factura amb un rebut pendent. Es creen sense els senyals de facturació
        (que generen rebuts i canvien estats): aquí es prova només la comparació."""
        from billing.models import Payment

        [invoice] = Invoice.objects.bulk_create([Invoice(
            serie_final=number, serie_token_final="FC", type=self.invoice_type, contract=self.contract,
            issue_date=datetime.date(2026, 11, 1), due_date=datetime.date(2026, 11, 30),
            payment_type_token_final="DD", status=status or self.confirmed, token=f"tok-{number}", **kwargs
        )])
        InvoiceLineItem.objects.bulk_create([InvoiceLineItem(invoice=invoice, price=100, tax_percent=10, tax_price=10)])
        [payment] = Payment.objects.bulk_create([Payment(
            invoice=invoice, contract=self.contract, amount=110, status=self.payment_pending, token=f"pay-{number}"
        )])
        return invoice, payment

    def _update_payment(self, payment, **fields):
        from billing.models import Payment

        Payment.objects.filter(pk=payment.pk).update(**fields)

    def _scan(self):
        from integrations.outbound.webhooks.invoice_status import scan

        with self.captureOnCommitCallbacks(execute=True):
            return scan()

    def _events(self, event_type=None):
        events_qs = WebhookEvent.objects.order_by("id")
        if event_type:
            events_qs = events_qs.filter(event_type=event_type)
        return list(events_qs)

    def test_first_scan_takes_the_photo_without_notifying(self, schedule):
        from integrations.models import WebhookInvoiceState

        self._invoice("FC/1", status=self.paid)
        result = self._scan()
        self.assertEqual(result["status"], "seeded")
        self.assertEqual(WebhookInvoiceState.objects.count(), 1)
        self.assertFalse(WebhookEvent.objects.exists())
        self.assertEqual(self._scan(), {"status": "success", "changes": 0, "events": 0})
        schedule.assert_not_called()

    def test_paid_invoice(self, schedule):
        invoice, payment = self._invoice("FC/2")
        self._scan()

        self._update_payment(payment, status=self.payment_paid, payment_date=datetime.date(2026, 11, 20))
        Invoice.objects.filter(pk=invoice.pk).update(status=self.paid)
        result = self._scan()

        self.assertEqual(result["events"], 1)
        schedule.assert_called_once()
        event = self._events("invoice.paid")[0]
        self.assertEqual(event.object_type, "invoices")
        data = event.payload["data"]
        self.assertEqual((data["part"], data["parts"]), (1, 1))
        item = data["invoices"][0]
        self.assertEqual(item["id"], invoice.id)
        self.assertEqual(item["token"], "tok-FC/2")
        self.assertEqual(item["number"], "FC/2")
        self.assertEqual(item["contract"], {"id": self.contract.id, "code": "C-STATUS"})
        self.assertEqual(item["holder"], {"id": self.holder.id})
        self.assertEqual(item["previous_status"], {"token": "I_CONFIRMED", "name": "Confirmada"})
        self.assertEqual(item["status"], {"token": "I_PAID", "name": "Pagada"})
        self.assertTrue(item["direct_debit"])
        self.assertEqual(item["amounts"], {"total": "110.00", "paid": "110.00", "pending": "0.00", "currency": "EUR"})
        self.assertEqual(item["payment_date"], "2026-11-20")
        self.assertIsNone(item["return"])
        # Ja avisada: no es repeteix
        self.assertEqual(self._scan()["events"], 0)

    def test_returned_receipt(self, _schedule):
        invoice, payment = self._invoice("FC/3")
        self._scan()

        self._update_payment(
            payment, status=self.payment_returned, reject_date=datetime.date(2026, 11, 21), reject=self.reject
        )
        self._scan()

        item = self._events("invoice.returned")[0].payload["data"]["invoices"][0]
        self.assertEqual(item["id"], invoice.id)
        self.assertEqual(item["status"]["token"], "I_CONFIRMED")
        self.assertEqual(item["amounts"]["pending"], "110.00")
        self.assertIsNone(item["payment_date"])
        self.assertEqual(
            item["return"], {"date": "2026-11-21", "reason": {"code": "AM04", "name": "Fons insuficients"}}
        )
        self.assertEqual(len(self._events()), 1)

    def test_returned_wins_over_status_change(self, _schedule):
        _invoice, payment = self._invoice("FC/4")
        self._scan()

        self._update_payment(payment, status=self.payment_returned)
        Invoice.objects.filter(pk=_invoice.pk).update(status=self.expired)
        self._scan()

        self.assertEqual([event.event_type for event in self._events()], ["invoice.returned"])

    def test_expired_and_cancelled(self, _schedule):
        expired, _ = self._invoice("FC/5")
        cancelled, _ = self._invoice("FC/6")
        dropped, _ = self._invoice("FC/6B")
        self._scan()

        Invoice.objects.filter(pk=expired.pk).update(status=self.expired)
        Invoice.objects.filter(pk=cancelled.pk).update(status=self.cancelled)
        Invoice.objects.filter(pk=dropped.pk).update(status=self.dropped)
        self._scan()

        self.assertEqual(self._events("invoice.expired")[0].payload["data"]["invoices"][0]["id"], expired.id)
        # Abonada i anul·lada van al mateix avís; l'estat diu quina
        items = self._events("invoice.cancelled")[0].payload["data"]["invoices"]
        self.assertEqual(
            [(item["id"], item["status"]["token"]) for item in items],
            [(cancelled.id, "I_CANCELLED"), (dropped.id, "I_DROPPED")],
        )

    def test_only_the_final_status_between_two_scans(self, _schedule):
        invoice, _ = self._invoice("FC/7")
        self._scan()

        Invoice.objects.filter(pk=invoice.pk).update(status=self.expired)
        Invoice.objects.filter(pk=invoice.pk).update(status=self.paid)
        self._scan()

        self.assertEqual([event.event_type for event in self._events()], ["invoice.paid"])

    def test_back_to_previous_status_between_two_scans_is_not_notified(self, _schedule):
        invoice, _ = self._invoice("FC/8")
        self._scan()

        Invoice.objects.filter(pk=invoice.pk).update(status=self.paid)
        Invoice.objects.filter(pk=invoice.pk).update(status=self.confirmed)
        self._scan()

        self.assertFalse(WebhookEvent.objects.exists())

    def test_unnumbered_budget_and_inactive_are_not_notified(self, _schedule):
        from integrations.models import WebhookInvoiceState

        draft, _ = self._invoice("TMP")
        Invoice.objects.filter(pk=draft.pk).update(serie_final=None)
        budget, _ = self._invoice("P/1")
        Invoice.objects.filter(pk=budget.pk).update(type=self.budget_type)
        inactive, _ = self._invoice("FC/9")
        Invoice.objects.filter(pk=inactive.pk).update(is_active=False)
        self._scan()

        Invoice.objects.filter(pk__in=[draft.pk, budget.pk, inactive.pk]).update(status=self.paid)
        result = self._scan()

        self.assertEqual(result["changes"], 3)
        self.assertFalse(WebhookEvent.objects.exists())
        # La foto sí que s'actualitza: no es tornen a detectar
        self.assertEqual(WebhookInvoiceState.objects.filter(status_id=self.paid.id).count(), 3)
        self.assertEqual(self._scan()["changes"], 0)

    def test_new_invoice_after_the_photo(self, _schedule):
        self._invoice("FC/10")
        self._scan()

        new_paid, _ = self._invoice("FC/11", status=self.paid)
        self._invoice("FC/12")
        self._scan()

        events_ = self._events()
        self.assertEqual([event.event_type for event in events_], ["invoice.paid"])
        item = events_[0].payload["data"]["invoices"][0]
        self.assertEqual(item["id"], new_paid.id)
        self.assertIsNone(item["previous_status"])

    @override_settings(WEBHOOKS_BILLING_CHUNK_SIZE=2)
    def test_changes_in_chunks(self, schedule):
        invoices = [self._invoice(f"FC/2{n}")[0] for n in range(3)]
        self._scan()

        Invoice.objects.filter(pk__in=[invoice.pk for invoice in invoices]).update(status=self.paid)
        result = self._scan()

        self.assertEqual(result["events"], 2)
        schedule.assert_called_once()
        parts = [event.payload["data"] for event in self._events("invoice.paid")]
        self.assertEqual([(part["part"], part["parts"]) for part in parts], [(1, 2), (2, 2)])
        self.assertEqual(
            [item["id"] for part in parts for item in part["invoices"]], [invoice.id for invoice in invoices]
        )
        self.assertEqual(self._events("invoice.paid")[0].object_id, f"{invoices[0].id}-{invoices[1].id}")

    @override_settings(WEBHOOKS_INVOICE_SCAN_LIMIT=2)
    def test_limit_leaves_the_rest_for_the_next_scan(self, _schedule):
        invoices = [self._invoice(f"FC/3{n}")[0] for n in range(3)]
        self._scan()

        Invoice.objects.filter(pk__in=[invoice.pk for invoice in invoices]).update(status=self.paid)
        self.assertEqual(self._scan()["changes"], 2)
        self.assertEqual(self._scan()["changes"], 1)
        self.assertEqual(self._scan()["changes"], 0)
        notified = [item["id"] for event in self._events() for item in event.payload["data"]["invoices"]]
        self.assertEqual(notified, [invoice.id for invoice in invoices])

    def test_chunk_that_cannot_be_built_is_retried(self, _schedule):
        invoice, _ = self._invoice("FC/40")
        self._scan()
        Invoice.objects.filter(pk=invoice.pk).update(status=self.paid)

        with mock.patch(
            "integrations.outbound.webhooks.invoice_status.invoice_status_data", side_effect=ValueError("error")
        ):
            result = self._scan()
        self.assertEqual((result["events"], result["retry"]), (0, 1))
        self.assertFalse(WebhookEvent.objects.exists())

        self._scan()
        self.assertEqual(len(self._events("invoice.paid")), 1)

    @override_settings(WEBHOOKS_ENABLED=False)
    def test_disabled_does_nothing(self, _schedule):
        from integrations.models import WebhookInvoiceState

        self._invoice("FC/50")
        self.assertEqual(self._scan(), {"status": "skipped"})
        self.assertFalse(WebhookInvoiceState.objects.exists())

    def test_baseline_command_resets_the_photo_without_notifying(self, _schedule):
        invoice, _ = self._invoice("FC/60")
        self._scan()
        Invoice.objects.filter(pk=invoice.pk).update(status=self.paid)

        out = io.StringIO()
        call_command("webhooks_invoice_baseline", stdout=out)

        self.assertIn("1", out.getvalue())
        self.assertEqual(self._scan()["changes"], 0)
        self.assertFalse(WebhookEvent.objects.exists())

    def test_task_runs_the_scan(self, _schedule):
        from integrations.outbound.webhooks.tasks import scan_invoice_status_webhooks

        self._invoice("FC/70")
        self.assertEqual(scan_invoice_status_webhooks()["status"], "seeded")


@ACTIVE
@mock.patch("integrations.outbound.webhooks.dispatcher.schedule_send")
class ContractRequestCancelledTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        from contract.models import ContractRequestStatus

        ConfigProject.objects.update_or_create(token="contract_request_cancel_token", defaults={"value": "CR_CANCEL"})
        cls.draft = ContractRequestStatus.objects.create(token="CR_DRAFT", name="Esborrany")
        cls.other = ContractRequestStatus.objects.create(token="CR_OTHER", name="En tràmit")
        cls.cancel = ContractRequestStatus.objects.create(token="CR_CANCEL", name="Anul·lada")

    def test_cancelling_emits_once(self, _schedule):
        request_obj = ContractRequest.objects.create(token="CR-10", status=self.draft)
        request_obj.status = self.other
        request_obj.save()
        self.assertFalse(WebhookEvent.objects.exists())

        request_obj.status = self.cancel
        request_obj.save()
        # Desar-la de nou sense canviar l'estat no repeteix l'avís
        request_obj.save()

        event = WebhookEvent.objects.get(event_type="contract_request.cancelled")
        self.assertEqual(event.object_type, "contract_request")
        self.assertEqual(
            event.payload["data"],
            {
                "contract_request": {"id": request_obj.id, "code": "CR-10"},
                "status": {"token": "CR_CANCEL", "name": "Anul·lada"},
            },
        )

    def test_reopened_and_cancelled_again_emits_again(self, _schedule):
        request_obj = ContractRequest.objects.create(token="CR-11", status=self.cancel)
        self.assertFalse(WebhookEvent.objects.exists())
        request_obj.status = self.draft
        request_obj.save()
        request_obj.status = self.cancel
        request_obj.save()
        self.assertEqual(WebhookEvent.objects.filter(event_type="contract_request.cancelled").count(), 1)

        request_obj = ContractRequest.objects.get(pk=request_obj.pk)
        request_obj.status = self.draft
        request_obj.save()
        request_obj.status = self.cancel
        request_obj.save()
        self.assertEqual(WebhookEvent.objects.filter(event_type="contract_request.cancelled").count(), 2)

    @override_settings(WEBHOOKS_ENABLED=False)
    def test_disabled_does_nothing(self, _schedule):
        request_obj = ContractRequest.objects.create(token="CR-12", status=self.draft)
        request_obj.status = self.cancel
        request_obj.save()
        self.assertFalse(WebhookEvent.objects.exists())
