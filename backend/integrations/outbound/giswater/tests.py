from unittest.mock import MagicMock, patch

import requests
from django.test import TestCase, override_settings
from requests.auth import HTTPBasicAuth

from integrations.models import IntegrationRequestLog
from integrations.outbound.giswater.auth import (
    get_access_token,
    get_basic_auth,
    get_http_auth,
    uses_keycloak,
)
from integrations.outbound.giswater.client import GiswaterClient
from integrations.outbound.giswater.exceptions import GiswaterApiError, GiswaterAuthError
from integrations.outbound.giswater.services import fetch_connecs

GISWATER_KEYCLOAK_SETTINGS = {
    "GISWATER_KEYCLOAK_URL": "https://keycloak.example.com/auth",
    "GISWATER_REALM": "test-realm",
    "GISWATER_CLIENT_ID": "aqua360",
    "GISWATER_CLIENT_SECRET": "secret",
}

GISWATER_BASIC_SETTINGS = {
    "GISWATER_KEYCLOAK_URL": "",
    "GISWATER_USERNAME": "giswater_user",
    "GISWATER_PASSWORD": "giswater_pass",
}


@override_settings(
    GISWATER_BASE_URL="https://giswater.example.com",
    GISWATER_TOKEN="test-token",
    GISWATER_TIMEOUT=10,
    **GISWATER_KEYCLOAK_SETTINGS,
)
class GiswaterClientTest(TestCase):
    @patch("integrations.outbound.giswater.client.requests.get")
    def test_get_list_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": 1}]}
        mock_get.return_value = mock_response

        client = GiswaterClient()
        result = client.get_list(schema="ws", table_name="ve_connec")

        self.assertEqual(result, {"data": [{"id": 1}]})
        mock_get.assert_called_once_with(
            "https://giswater.example.com/basic/getlist",
            params={"schema": "ws", "tableName": "ve_connec"},
            headers={
                "Accept": "application/json",
                "Authorization": "Bearer test-token",
            },
            auth=None,
            timeout=10,
        )

        log = IntegrationRequestLog.objects.get()
        self.assertEqual(log.provider, "giswater")
        self.assertEqual(log.direction, IntegrationRequestLog.DIRECTION_OUTBOUND)
        self.assertTrue(log.success)
        self.assertEqual(log.status_code, 200)

    @patch("integrations.outbound.giswater.client.requests.get")
    def test_get_list_http_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response

        client = GiswaterClient()
        with self.assertRaises(GiswaterApiError):
            client.get_list(schema="ws", table_name="ve_connec")

        log = IntegrationRequestLog.objects.get()
        self.assertFalse(log.success)
        self.assertEqual(log.status_code, 500)

    @patch("integrations.outbound.giswater.client.requests.get")
    def test_get_list_connection_error(self, mock_get):
        mock_get.side_effect = requests.RequestException("Connection failed")

        client = GiswaterClient()
        with self.assertRaises(GiswaterApiError):
            client.get_list(schema="ws", table_name="ve_connec")

        log = IntegrationRequestLog.objects.get()
        self.assertFalse(log.success)
        self.assertIn("Connection failed", log.error_message)

    @override_settings(GISWATER_TOKEN="")
    @patch("integrations.outbound.giswater.client.get_http_auth")
    @patch("integrations.outbound.giswater.client.requests.get")
    def test_get_list_uses_keycloak_token(self, mock_get, mock_get_http_auth):
        mock_get_http_auth.return_value = (
            {"Authorization": "Bearer oauth-token"},
            None,
        )
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_get.return_value = mock_response

        client = GiswaterClient()
        client.get_list(schema="ws", table_name="ve_connec")

        mock_get_http_auth.assert_called_once()
        mock_get.assert_called_once()
        self.assertEqual(
            mock_get.call_args.kwargs["headers"]["Authorization"],
            "Bearer oauth-token",
        )
        self.assertIsNone(mock_get.call_args.kwargs["auth"])

    @override_settings(GISWATER_TOKEN="", **GISWATER_BASIC_SETTINGS)
    @patch("integrations.outbound.giswater.client.requests.get")
    def test_get_list_uses_basic_auth(self, mock_get):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_get.return_value = mock_response

        client = GiswaterClient()
        client.get_list(schema="ws", table_name="ve_connec")

        mock_get.assert_called_once()
        self.assertNotIn("Authorization", mock_get.call_args.kwargs["headers"])
        auth = mock_get.call_args.kwargs["auth"]
        self.assertIsInstance(auth, HTTPBasicAuth)
        self.assertEqual(auth.username, "giswater_user")
        self.assertEqual(auth.password, "giswater_pass")


@override_settings(GISWATER_TIMEOUT=10, **GISWATER_KEYCLOAK_SETTINGS)
class GiswaterAuthTest(TestCase):
    @patch("integrations.outbound.giswater.auth.requests.post")
    def test_get_access_token_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "abc123"}
        mock_post.return_value = mock_response

        token = get_access_token()

        self.assertEqual(token, "abc123")
        mock_post.assert_called_once_with(
            "https://keycloak.example.com/auth/realms/test-realm/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": "aqua360",
                "client_secret": "secret",
            },
            timeout=10,
        )

    @patch("integrations.outbound.giswater.auth.requests.post")
    def test_get_access_token_missing_token_in_response(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {}
        mock_post.return_value = mock_response

        with self.assertRaises(GiswaterAuthError):
            get_access_token()

    @override_settings(GISWATER_CLIENT_SECRET="")
    def test_get_access_token_missing_credentials(self):
        with self.assertRaises(GiswaterAuthError):
            get_access_token()

    def test_uses_keycloak_when_url_set(self):
        self.assertTrue(uses_keycloak())

    @override_settings(**GISWATER_BASIC_SETTINGS)
    def test_uses_keycloak_false_when_url_empty(self):
        self.assertFalse(uses_keycloak())

    @override_settings(**GISWATER_BASIC_SETTINGS)
    def test_get_basic_auth_success(self):
        auth = get_basic_auth()
        self.assertIsInstance(auth, HTTPBasicAuth)
        self.assertEqual(auth.username, "giswater_user")
        self.assertEqual(auth.password, "giswater_pass")

    @override_settings(GISWATER_KEYCLOAK_URL="", GISWATER_USERNAME="", GISWATER_PASSWORD="")
    def test_get_basic_auth_missing_credentials(self):
        with self.assertRaises(GiswaterAuthError):
            get_basic_auth()

    @override_settings(**GISWATER_BASIC_SETTINGS)
    def test_get_http_auth_falls_back_to_basic(self):
        headers, auth = get_http_auth()
        self.assertEqual(headers, {})
        self.assertIsInstance(auth, HTTPBasicAuth)
        self.assertEqual(auth.username, "giswater_user")

    @patch("integrations.outbound.giswater.auth.get_access_token")
    def test_get_http_auth_uses_keycloak_when_configured(self, mock_get_token):
        mock_get_token.return_value = "oauth-token"
        headers, auth = get_http_auth()
        self.assertEqual(headers, {"Authorization": "Bearer oauth-token"})
        self.assertIsNone(auth)
        mock_get_token.assert_called_once()


@override_settings(
    GISWATER_BASE_URL="https://giswater.example.com",
    GISWATER_TOKEN="",
    GISWATER_TIMEOUT=10,
)
class FetchConnecsTest(TestCase):
    @patch("integrations.outbound.giswater.services.GiswaterClient")
    def test_fetch_connecs(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.get_list.return_value = {"data": []}
        mock_client_class.return_value = mock_client

        result = fetch_connecs()

        self.assertEqual(result, {"data": []})
        mock_client.get_list.assert_called_once_with(
            schema="ws",
            table_name="ve_connec",
        )
