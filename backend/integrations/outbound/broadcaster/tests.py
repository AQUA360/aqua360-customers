from unittest.mock import MagicMock, patch

import requests
from django.test import TestCase, override_settings

from integrations.models import IntegrationRequestLog
from integrations.outbound.broadcaster.client import BroadcasterClient
from integrations.outbound.broadcaster.exceptions import BroadcasterError


@override_settings(
    BROADCASTER_API_URL="https://broadcaster.test/send/",
    BROADCASTER_API_TOKEN="test-token",
    BROADCASTER_TIMEOUT_SECONDS=10,
    BROADCASTER_USER_AGENT="",
    BROADCASTER_CHANNEL="sms",
    BROADCASTER_TOPIC="aqua360-customers",
    BROADCASTER_TEMPLATE_CODE="aqua360-customers",
    BROADCASTER_TEMPLATE_NAME="Comunicació",
    BROADCASTER_TEMPLATE_BODY="{{ message }}",
)
class BroadcasterClientTest(TestCase):
    @patch("integrations.outbound.broadcaster.client.requests.post")
    def test_send_sms_payload(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)

        BroadcasterClient().send_sms(
            recipient_name="Anna Test",
            phones=["612 34 56 78", "+33 6 12 34 56 78"],
            text="Avís de prova",
            object_type="communication",
            object_id="1",
        )

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://broadcaster.test/send/")
        payload = kwargs["json"]
        self.assertEqual(payload["channel"], "sms")
        self.assertEqual(payload["topic"], "aqua360-customers")
        self.assertEqual(payload["template"]["body"], "{{ message }}")
        self.assertEqual(payload["template"]["subject"], payload["template"]["name"])
        self.assertEqual(payload["template"]["available_variables"], ["message"])
        self.assertEqual(
            payload["recipients"],
            [
                {"name": "Anna Test", "value": "34612345678", "context": {"message": "Avís de prova"}},
                {"name": "Anna Test", "value": "33612345678", "context": {"message": "Avís de prova"}},
            ],
        )
        self.assertEqual(kwargs["headers"]["Authorization"], "Token test-token")
        self.assertIn("Mozilla", kwargs["headers"]["User-Agent"])
        self.assertEqual(kwargs["timeout"], 10)

        log = IntegrationRequestLog.objects.get(provider="broadcaster")
        self.assertTrue(log.success)
        # Sense telèfons ni text al registre.
        self.assertEqual(log.request_payload, {})

    @patch("integrations.outbound.broadcaster.client.requests.post")
    def test_http_error(self, mock_post):
        mock_post.return_value = MagicMock(status_code=403, text="Forbidden")

        with self.assertRaises(BroadcasterError):
            BroadcasterClient().send_sms(recipient_name="Anna", phones=["612345678"], text="Hola")

        log = IntegrationRequestLog.objects.get(provider="broadcaster")
        self.assertFalse(log.success)
        self.assertEqual(log.status_code, 403)

    @patch("integrations.outbound.broadcaster.client.requests.post")
    def test_connection_error(self, mock_post):
        mock_post.side_effect = requests.ConnectionError("down")

        with self.assertRaises(BroadcasterError):
            BroadcasterClient().send_sms(recipient_name="Anna", phones=["612345678"], text="Hola")

    @patch("integrations.outbound.broadcaster.client.requests.post")
    def test_landline_is_not_sent(self, mock_post):
        with self.assertRaises(BroadcasterError):
            BroadcasterClient().send_sms(recipient_name="Anna", phones=["972123456"], text="Hola")
        mock_post.assert_not_called()

    @patch("integrations.outbound.broadcaster.client.requests.post")
    def test_without_phones_or_token(self, mock_post):
        with self.assertRaises(BroadcasterError):
            BroadcasterClient().send_sms(recipient_name="Anna", phones=[], text="Hola")
        with override_settings(BROADCASTER_API_TOKEN=""):
            with self.assertRaises(BroadcasterError):
                BroadcasterClient().send_sms(recipient_name="Anna", phones=["612345678"], text="Hola")
        mock_post.assert_not_called()
