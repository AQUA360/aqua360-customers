import json
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from communication.views.sms_callback_view import (
    SMS_CALLBACK_MAX_BODY_BYTES,
    SmsCallbackThrottle,
    SmsCallbackView,
)

URL = '/communication/sms-callback/'


class SmsCallbackViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def tearDown(self):
        cache.clear()

    def test_public_post_is_accepted(self):
        response = self.client.post(URL, {'status': 'delivered'}, format='json')
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {'ok': 'ok'})

    def test_does_not_print_request_data(self):
        with patch('sys.stdout', new_callable=StringIO) as stdout:
            self.client.post(URL, {'marker': 'texte-que-no-ha-de-sortir'}, format='json')
        self.assertNotIn('texte-que-no-ha-de-sortir', stdout.getvalue())

    def test_does_not_log_request_data(self):
        with self.assertNoLogs(level='DEBUG'):
            self.client.post(URL, {'marker': 'texte-que-no-ha-de-sortir'}, format='json')

    def test_body_at_limit_is_accepted(self):
        filler = 'a' * (SMS_CALLBACK_MAX_BODY_BYTES - len(json.dumps({'x': ''})))
        body = json.dumps({'x': filler})
        self.assertEqual(len(body), SMS_CALLBACK_MAX_BODY_BYTES)
        response = self.client.post(URL, body, content_type='application/json')
        self.assertEqual(response.status_code, 202)

    def test_body_over_limit_is_rejected(self):
        body = json.dumps({'x': 'a' * SMS_CALLBACK_MAX_BODY_BYTES})
        response = self.client.post(URL, body, content_type='application/json')
        self.assertEqual(response.status_code, 413)

    def test_invalid_content_length_is_rejected(self):
        body = 'a'
        response = self.client.generic(
            'POST', URL, body, content_type='text/plain',
            CONTENT_LENGTH='no-numeric',
        )
        self.assertEqual(response.status_code, 413)

    def test_get_is_not_allowed(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 405)

    def test_uses_dedicated_throttle(self):
        self.assertEqual(SmsCallbackView.throttle_classes, [SmsCallbackThrottle])
        self.assertEqual(SmsCallbackThrottle.rate, '60/min')

    def test_throttles_after_limit_per_ip(self):
        for _ in range(60):
            response = self.client.post(URL, {}, format='json', REMOTE_ADDR='10.0.0.1')
            self.assertEqual(response.status_code, 202)
        response = self.client.post(URL, {}, format='json', REMOTE_ADDR='10.0.0.1')
        self.assertEqual(response.status_code, 429)

        # Una altra IP no queda afectada.
        response = self.client.post(URL, {}, format='json', REMOTE_ADDR='10.0.0.2')
        self.assertEqual(response.status_code, 202)

    def test_authenticated_user_is_also_throttled(self):
        user = User.objects.create_user(username='sms-callback-test', password='x')
        self.client.force_authenticate(user)
        for _ in range(60):
            self.client.post(URL, {}, format='json', REMOTE_ADDR='10.0.0.3')
        response = self.client.post(URL, {}, format='json', REMOTE_ADDR='10.0.0.3')
        self.assertEqual(response.status_code, 429)
