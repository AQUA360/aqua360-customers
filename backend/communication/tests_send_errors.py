"""Motius de rebuig llegibles dels enviaments (correu i SMS) i compatibilitat de django-msgraphbackend."""
import io
import os
import subprocess
import sys
import json
import smtplib
import socket
import ssl
import urllib.error
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from django.utils import translation

from communication.utils import send_errors
from communication.utils.send_errors import (
  email_generic_error, email_rejection_reason, graph_error_info, patch_httperror_add_note, sms_rejection_reason,
)
from integrations.outbound.broadcaster.exceptions import BroadcasterError

GRAPH_SEND_URL = "https://graph.microsoft.com/v1.0/users/user-id/sendMail"
GRAPH_TOKEN_URL = "https://login.microsoftonline.com/tenant/oauth2/v2.0/token"


def graph_http_error(status, code=None, message="detail", url=GRAPH_SEND_URL):
  body = json.dumps({"error": {"code": code, "message": message}}).encode() if code else b"<html>error</html>"
  return urllib.error.HTTPError(url, status, "Error", {}, io.BytesIO(body))


def msgraph_send(error):
  """Envia un correu amb MSGraphBackend fent que Graph respongui amb `error`; retorna l'excepció."""
  from django.core.mail import EmailMessage
  from msgraphbackend import MSGraphBackend

  token = MagicMock()
  token.read.return_value = json.dumps({
    "token_type": "Bearer", "expires_in": 3600, "ext_expires_in": 3600, "access_token": "x",
  }).encode()
  with override_settings(
    MSGRAPH_TENANT_ID="tenant", MSGRAPH_CLIENT_ID="client", MSGRAPH_CLIENT_SECRET="secret", MSGRAPH_USER_ID="user-id",
  ), patch("urllib.request.urlopen", side_effect=[token, error]):
    backend = MSGraphBackend()
    message = EmailMessage("Assumpte", "Cos", "sender@example.com", ["recipient@example.com"], connection=backend)
    try:
      message.send(fail_silently=False)
    except Exception as exc:
      return exc
  raise AssertionError("L'enviament no ha fallat")


class HttpErrorAddNoteTests(SimpleTestCase):
  def test_patch_is_applied_at_startup(self):
    # En un procés nou, perquè cap altre test l'hagi aplicat abans: només
    # CommunicationConfig.ready() (via django.setup()) l'ha d'haver instal·lat.
    code = (
      "import django, urllib.error; django.setup(); "
      "print('add_note' in urllib.error.HTTPError.__dict__ or hasattr(Exception, 'add_note'))"
    )
    result = subprocess.run(
      [sys.executable, "-c", code],
      cwd=settings.BASE_DIR, capture_output=True, text=True, timeout=120,
      env={**os.environ, "DJANGO_SETTINGS_MODULE": os.environ.get("DJANGO_SETTINGS_MODULE", "customers.settings")},
    )
    self.assertEqual(result.returncode, 0, result.stderr[-2000:])
    self.assertEqual(result.stdout.strip().splitlines()[-1], "True")

  def test_add_note_keeps_the_note(self):
    patch_httperror_add_note()
    error = graph_http_error(400, "ErrorInvalidRecipients")
    error.add_note("ErrorInvalidRecipients: detail")
    self.assertEqual(error.__dict__.get("__notes__"), ["ErrorInvalidRecipients: detail"])

  def test_patch_is_idempotent(self):
    patch_httperror_add_note()
    add_note = getattr(urllib.error.HTTPError, "add_note")
    patch_httperror_add_note()
    self.assertIs(getattr(urllib.error.HTTPError, "add_note"), add_note)

  def test_msgraph_backend_raises_the_real_graph_error(self):
    exc = msgraph_send(graph_http_error(400, "ErrorInvalidRecipients", "At least one recipient is not valid."))

    self.assertIsInstance(exc, urllib.error.HTTPError)
    self.assertEqual(graph_error_info(exc), (400, "ErrorInvalidRecipients", "At least one recipient is not valid.", GRAPH_SEND_URL))
    self.assertEqual(email_rejection_reason(exc), send_errors._invalid_recipient())

  def test_msgraph_error_without_json_body_uses_http_status(self):
    exc = msgraph_send(graph_http_error(429))

    self.assertEqual(email_rejection_reason(exc), send_errors._throttled())


class EmailRejectionReasonTests(SimpleTestCase):
  CASES = (
    ("smtp recipient 550", smtplib.SMTPRecipientsRefused({"a@example.com": (550, b"5.1.1 User unknown")}), "_recipient_rejected"),
    ("smtp mailbox full", smtplib.SMTPRecipientsRefused({"a@example.com": (552, b"5.2.2 Mailbox full")}), "_mailbox_full"),
    ("smtp bad address", smtplib.SMTPRecipientsRefused({"a@": (501, b"5.1.3 Bad recipient address syntax")}), "_invalid_recipient"),
    ("smtp relay denied", smtplib.SMTPRecipientsRefused({"a@example.com": (550, b"5.7.1 Relaying denied")}), "_policy_rejected"),
    ("smtp auth", smtplib.SMTPAuthenticationError(535, b"5.7.8 Authentication credentials invalid"), "_auth_failed"),
    ("smtp sender", smtplib.SMTPSenderRefused(553, b"5.7.1 Sender address rejected", "s@example.com"), "_sender_rejected"),
    ("smtp sender mailbox full", smtplib.SMTPSenderRefused(552, b"5.2.2 Mailbox full", "s@example.com"), "_sender_quota"),
    ("smtp too large", smtplib.SMTPDataError(552, b"5.3.4 Message size exceeds fixed limit"), "_too_large"),
    ("smtp spam", smtplib.SMTPDataError(554, b"5.7.1 Message rejected as spam"), "_policy_rejected"),
    ("smtp rate limit", smtplib.SMTPDataError(421, b"4.7.0 Too many messages, rate limited"), "_throttled"),
    ("smtp daily quota", smtplib.SMTPDataError(550, b"5.4.5 Daily user sending quota exceeded"), "_throttled"),
    ("smtp busy", smtplib.SMTPDataError(451, b"4.3.0 Try again later"), "_temporarily_unavailable"),
    ("smtp disconnected", smtplib.SMTPServerDisconnected("Connection unexpectedly closed"), "_connection_failed"),
    ("smtp connect", smtplib.SMTPConnectError(421, b"Service not available"), "_temporarily_unavailable"),
    ("starttls", smtplib.SMTPNotSupportedError("STARTTLS extension not supported by server."), "_tls_failed"),
    ("refused", ConnectionRefusedError(111, "Connection refused"), "_connection_failed"),
    ("dns", socket.gaierror(-2, "Name or service not known"), "_connection_failed"),
    ("timeout", socket.timeout("timed out"), "_timeout"),
    ("ssl", ssl.SSLError(1, "[SSL: WRONG_VERSION_NUMBER] wrong version number"), "_tls_failed"),
    ("url timeout", urllib.error.URLError(socket.timeout("timed out")), "_timeout"),
    ("url refused", urllib.error.URLError(ConnectionRefusedError(111, "refused")), "_connection_failed"),
    ("graph invalid recipients", "ErrorInvalidRecipients", "_invalid_recipient"),
    ("graph mailbox not enabled", "MailboxNotEnabledForRESTAPI", "_sender_mailbox"),
    ("graph quota", "ErrorQuotaExceeded", "_sender_quota"),
    ("graph size", "ErrorMessageSizeExceeded", "_too_large"),
    ("graph send as", "ErrorSendAsDenied", "_permission_denied"),
    ("graph throttled", "ApplicationThrottled", "_throttled"),
    ("graph 401", 401, "_auth_failed"),
    ("graph 403", 403, "_permission_denied"),
    ("graph 404", 404, "_sender_mailbox"),
    ("graph 413", 413, "_too_large"),
    ("graph 429", 429, "_throttled"),
    ("graph 503", 503, "_temporarily_unavailable"),
    ("graph token", "token", "_auth_failed"),
    ("graph token throttled", "token429", "_throttled"),
    ("graph settings", ImproperlyConfigured("The MSGRAPH_TENANT_ID setting must be set."), "_service_misconfigured"),
    ("graph sender user", ValueError("No user found in Entra ID with the smtp address 's@example.com'."), "_sender_mailbox"),
    ("django address", ValueError('Invalid address "a@b@c"'), "_invalid_recipient"),
  )

  def build(self, error):
    if error == "token":
      return graph_http_error(401, url=GRAPH_TOKEN_URL)
    if error == "token429":
      return graph_http_error(429, url=GRAPH_TOKEN_URL)
    if isinstance(error, int):
      return graph_http_error(error)
    if isinstance(error, str):
      exc = graph_http_error(400, error)
      patch_httperror_add_note()
      exc.add_note(f"{error}: detail with a@example.com")
      return exc
    return error

  def test_known_errors(self):
    for name, error, expected in self.CASES:
      with self.subTest(name):
        exc = self.build(error)
        with self.assertLogs("communication.utils.send_errors", "WARNING"):
          reason = email_rejection_reason(exc, 1)
        self.assertEqual(reason, getattr(send_errors, expected)())
        self.assertNotIn(str(exc), reason)
        self.assertNotIn("@", reason)

  def test_graph_error_inside_json_decode_error(self):
    # Si el cos de l'error no és JSON, el backend falla en llegir-lo: l'HTTPError queda al context.
    try:
      try:
        raise graph_http_error(403)
      except urllib.error.HTTPError:
        json.loads("<html>")
    except ValueError as exc:
      self.assertEqual(email_rejection_reason(exc), send_errors._permission_denied())

  def test_unknown_error_is_generic_and_logged(self):
    exc = AttributeError("'HTTPResponse' object has no attribute 'add_note'")
    with self.assertLogs("communication.utils.send_errors", "ERROR") as logs:
      reason = email_rejection_reason(exc, 1)

    self.assertEqual(reason, email_generic_error())
    self.assertNotIn("add_note", reason)
    self.assertIn("add_note", "\n".join(logs.output))

  def test_unknown_smtp_code_is_generic(self):
    exc = smtplib.SMTPDataError(599, b"weird")
    with self.assertLogs("communication.utils.send_errors", "ERROR"):
      self.assertEqual(email_rejection_reason(exc), email_generic_error())


class SmsRejectionReasonTests(SimpleTestCase):
  def setUp(self):
    override = translation.override("en")
    override.__enter__()
    self.addCleanup(override.__exit__, None, None, None)

  def test_mapped_errors(self):
    cases = (
      (BroadcasterError("Error resposta Broadcaster 403: <html>", status_code=403), "credentials"),
      (BroadcasterError("Error resposta Broadcaster 429: slow down", status_code=429), "limited"),
      (BroadcasterError("Error resposta Broadcaster 502: bad gateway", status_code=502), "unavailable"),
    )
    for exc, word in cases:
      with self.subTest(word), self.assertLogs("communication.utils.send_errors", "WARNING"):
        reason = sms_rejection_reason(exc)
        self.assertIn(word, reason)
        self.assertNotIn(str(exc), reason)

  def test_connection_error(self):
    try:
      try:
        raise ConnectionError("Max retries exceeded with url")
      except ConnectionError as cause:
        raise BroadcasterError(f"Error connectant amb Broadcaster: {cause}") from cause
    except BroadcasterError as exc:
      with self.assertLogs("communication.utils.send_errors", "WARNING"):
        reason = sms_rejection_reason(exc)
    self.assertIn("could not connect", reason)
    self.assertNotIn("Max retries", reason)

  def test_user_message_is_kept(self):
    exc = BroadcasterError("L'SMS no té text.", user_message="user facing")
    with self.assertLogs("communication.utils.send_errors", "WARNING"):
      self.assertEqual(sms_rejection_reason(exc), "user facing")

  def test_unknown_error_is_generic(self):
    for exc in (BroadcasterError("Error resposta Broadcaster 400: raw", status_code=400), KeyError("full_name")):
      with self.subTest(type(exc).__name__), self.assertLogs("communication.utils.send_errors", "ERROR"):
        reason = sms_rejection_reason(exc)
        self.assertIn("Unknown error", reason)
        self.assertNotIn("raw", reason)
        self.assertNotIn("full_name", reason)
