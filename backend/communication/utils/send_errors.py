"""
Motius de rebuig llegibles per als enviaments de comunicacions (correu i SMS).

El detall tècnic de l'error (excepció, codi SMTP, resposta de Microsoft Graph...) només va al log;
a `rejection_reason` es desa un missatge curt i traduït que l'usuari pugui entendre.
"""
import logging
import smtplib
import socket
import ssl
import urllib.error
import urllib.parse

from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


def patch_httperror_add_note():
  """
  django-msgraphbackend 1.0.x fa `err.add_note()`, que no existeix fins a Python 3.11. A Python 3.10
  HTTPError delega els atributs que no té al cos de la resposta: l'AttributeError resultant
  ("'HTTPResponse' object has no attribute 'add_note'") amaga l'error real de Graph.
  Afegeix un add_note compatible que desa la nota a `__notes__`, com fa Python 3.11.
  """
  existing = getattr(urllib.error.HTTPError, "add_note", None)
  if existing is not None and getattr(existing, "__msgraph_compat__", False):
    return
  if getattr(Exception, "add_note", None) is not None:
    return

  def add_note(self, note):
    notes = self.__dict__.get("__notes__")
    if notes is None:
      notes = self.__notes__ = []
    notes.append(note)

  add_note.__msgraph_compat__ = True
  urllib.error.HTTPError.add_note = add_note


class EmailPreparationError(Exception):
  """Error en preparar el correu; el missatge ja és el motiu que veu l'usuari."""


def _email_error(detail):
  return _("The email could not be sent: %(detail)s") % {"detail": detail}


def email_generic_error():
  return _("The email could not be sent. Unknown error from the mail server.")


def email_preparation_error():
  return _("The email could not be prepared. Check the message and the company's email configuration.")


def email_no_company_config_error():
  return _("The email could not be sent: the communication has no company configuration.")


def email_no_recipient_error():
  return _("The email could not be sent: the recipient has no email address.")


def email_no_sender_error():
  return _("The email could not be sent: there is no sender address configured.")


def _invalid_recipient():
  return _email_error(_("the recipient's address is not valid."))


def _recipient_rejected():
  return _email_error(_("the mail server rejected the recipient's address (the mailbox does not exist or does not accept emails)."))


def _mailbox_full():
  return _email_error(_("the recipient's mailbox is full."))


def _too_large():
  return _email_error(_("the email is larger than the mail server allows. Reduce the size or the number of attachments."))


def _throttled():
  return _email_error(_("the mail server has temporarily limited the number of emails sent. Try again later."))


def _temporarily_unavailable():
  return _email_error(_("the mail server is temporarily unavailable. Try again later."))


def _auth_failed():
  return _email_error(_("the mail server rejected the sender's credentials. Check the email configuration."))


def _permission_denied():
  return _email_error(_("the email account is not allowed to send from the sender's address. Check the email configuration."))


def _sender_mailbox():
  return _email_error(_("the sender's mailbox does not exist or is not enabled to send emails."))


def _sender_quota():
  return _email_error(_("the sender's mailbox has exceeded its storage quota."))


def _sender_rejected():
  return _email_error(_("the mail server does not accept the sender's address."))


def _policy_rejected():
  return _email_error(_("the mail server rejected the message because of its policy (for example, a spam filter)."))


def _connection_failed():
  return _email_error(_("could not connect to the mail server. Check the server configuration or try again later."))


def _timeout():
  return _email_error(_("the mail server did not respond in time. Try again later."))


def _tls_failed():
  return _email_error(_("the secure connection (SSL/TLS) with the mail server failed. Check the SSL/TLS configuration."))


def _service_misconfigured():
  return _email_error(_("the email service is not configured correctly."))


# Codis d'error de Microsoft Graph (camp error.code de la resposta) que es coneixen.
_GRAPH_CODES = {
  "ErrorInvalidRecipients": _invalid_recipient,
  "ErrorInvalidRecipientsAddress": _invalid_recipient,
  "ErrorInvalidSmtpAddress": _invalid_recipient,
  "ErrorRecipientNotFound": _recipient_rejected,
  "MailboxNotEnabledForRESTAPI": _sender_mailbox,
  "MailboxNotSupportedForRESTAPI": _sender_mailbox,
  "ErrorNonExistentMailbox": _sender_mailbox,
  "ErrorInvalidUser": _sender_mailbox,
  "ResourceNotFound": _sender_mailbox,
  "ErrorQuotaExceeded": _sender_quota,
  "ErrorMessageSizeExceeded": _too_large,
  "ErrorSendAsDenied": _permission_denied,
  "ErrorAccessDenied": _permission_denied,
  "AccessDenied": _permission_denied,
  "Authorization_RequestDenied": _permission_denied,
  "InvalidAuthenticationToken": _auth_failed,
  "ErrorExceededMessageLimit": _throttled,
  "ApplicationThrottled": _throttled,
  "TooManyRequests": _throttled,
  "MailboxConcurrency": _throttled,
  "ErrorServerBusy": _temporarily_unavailable,
  "ServiceNotAvailable": _temporarily_unavailable,
}

_HTTP_STATUS = {
  401: _auth_failed,
  403: _permission_denied,
  404: _sender_mailbox,
  413: _too_large,
  429: _throttled,
}


def _iter_chain(exc):
  seen = set()
  while exc is not None and id(exc) not in seen:
    seen.add(id(exc))
    yield exc
    exc = exc.__cause__ or exc.__context__


def graph_error_info(exc):
  """
  (status HTTP, codi d'error de Graph, missatge de Graph, url) de l'HTTPError de la cadena, o None.

  Sobre HTTPError es llegeix `__dict__`: a Python 3.10 els atributs que no té van al cos de la resposta.
  """
  for current in _iter_chain(exc):
    if isinstance(current, urllib.error.HTTPError):
      code, message = None, None
      for note in current.__dict__.get("__notes__") or []:
        code, _sep, message = str(note).partition(": ")
      return current.__dict__.get("code"), code, message, current.__dict__.get("url") or ""
  return None


def _smtp_code_message(exc):
  """Codi i text SMTP de l'excepció; per a SMTPRecipientsRefused, els del primer destinatari."""
  if isinstance(exc, smtplib.SMTPRecipientsRefused):
    for code, message in (exc.recipients or {}).values():
      return code, message
    return None, b""
  return getattr(exc, "smtp_code", None), getattr(exc, "smtp_error", b"")


def _describe_smtp(exc):
  if isinstance(exc, smtplib.SMTPAuthenticationError):
    return _auth_failed()
  if isinstance(exc, smtplib.SMTPNotSupportedError):
    return _tls_failed()
  if isinstance(exc, smtplib.SMTPServerDisconnected):
    return _connection_failed()

  code, message = _smtp_code_message(exc)
  if isinstance(message, bytes):
    message = message.decode("utf-8", "replace")
  text = (message or "").lower()
  if code is None:
    return None

  if (code == 552 and ("size" in text or "5.3.4" in text)) or "message too big" in text:
    return _too_large()
  if "5.4.5" in text or "sending quota" in text or "sending limit" in text:
    return _throttled()
  if "5.2.2" in text or "full" in text or "quota" in text or "insufficient storage" in text:
    return _mailbox_full()
  if code in (421, 450, 451, 452) and ("rate" in text or "too many" in text or "limit" in text or "4.7.0" in text):
    return _throttled()
  if code in (421, 450, 451, 452):
    return _temporarily_unavailable()
  if code in (530, 534, 535):
    return _auth_failed()
  if isinstance(exc, smtplib.SMTPSenderRefused):
    return _sender_rejected()
  if "5.7." in text or "spam" in text or "policy" in text or "blocked" in text:
    return _policy_rejected()
  if code in (501, 553) or "5.1.3" in text:
    return _invalid_recipient()
  if isinstance(exc, smtplib.SMTPRecipientsRefused) or code in (550, 551) or "5.1.1" in text:
    return _recipient_rejected()
  if code == 554:
    return _policy_rejected()
  return None


def _describe_graph(exc):
  info = graph_error_info(exc)
  if info is None:
    return None
  status, code, _message, url = info
  if urllib.parse.urlsplit(url or "").hostname == "login.microsoftonline.com":
    # Error en demanar el token: credencials (tenant, client id o secret) incorrectes.
    return _auth_failed() if status and status < 500 else _temporarily_unavailable()
  if code in _GRAPH_CODES:
    return _GRAPH_CODES[code]()
  if status in _HTTP_STATUS:
    return _HTTP_STATUS[status]()
  if status and status >= 500:
    return _temporarily_unavailable()
  return None


def _describe_network(exc):
  for current in _iter_chain(exc):
    if isinstance(current, urllib.error.HTTPError):
      return None
    if isinstance(current, urllib.error.URLError):
      reason = current.reason
      if isinstance(reason, (socket.timeout, TimeoutError)):
        return _timeout()
      if isinstance(reason, ssl.SSLError):
        return _tls_failed()
      return _connection_failed()
    if isinstance(current, (socket.timeout, TimeoutError)):
      return _timeout()
    if isinstance(current, ssl.SSLError):
      return _tls_failed()
    if isinstance(current, (smtplib.SMTPConnectError, socket.gaierror, ConnectionError)):
      return _connection_failed()
  return None


def describe_email_error(exc):
  """Motiu llegible (traduït) d'un error d'enviament de correu, o el genèric si no es coneix."""
  for current in _iter_chain(exc):
    if isinstance(current, smtplib.SMTPException):
      message = _describe_smtp(current)
      if message:
        return message
  message = _describe_graph(exc) or _describe_network(exc)
  if message:
    return message
  if isinstance(exc, ImproperlyConfigured):
    return _service_misconfigured()
  if isinstance(exc, ValueError) and "No user found in Entra ID" in str(exc):
    # django-msgraphbackend no troba cap usuari amb l'adreça del remitent.
    return _sender_mailbox()
  if isinstance(exc, ValueError) and "invalid address" in str(exc).lower():
    # Django no pot formar la capçalera amb l'adreça (mal escrita, amb salts de línia...).
    return _invalid_recipient()
  return None


def email_rejection_reason(exc, comm_id=None, context=""):
  """Motiu que es desa a la comunicació; el detall tècnic (i `context`) va al log."""
  message = describe_email_error(exc)
  graph = graph_error_info(exc)
  detail = f" ({context})" if context else ""
  if graph:
    detail += f" [Graph HTTP {graph[0]} {graph[1] or ''}: {graph[2] or ''}]"
  if message:
    logger.warning("Error enviant la comunicació %s per correu%s: %r", comm_id, detail, exc)
    return message
  logger.error("Error desconegut enviant la comunicació %s per correu%s", comm_id, detail, exc_info=exc)
  return email_generic_error()


def sms_rejection_reason(exc, comm_id=None):
  """Motiu que es desa a la comunicació si l'SMS falla; el detall tècnic va al log."""
  from integrations.outbound.broadcaster.exceptions import BroadcasterError

  if isinstance(exc, BroadcasterError):
    status = exc.status_code
    if exc.user_message:
      message = exc.user_message
    elif status in (401, 403):
      message = _("The SMS could not be sent: the SMS service rejected the credentials. Check the SMS configuration.")
    elif status == 429:
      message = _("The SMS could not be sent: the SMS service has temporarily limited the number of messages. Try again later.")
    elif status and status >= 500:
      message = _("The SMS could not be sent: the SMS service is temporarily unavailable. Try again later.")
    elif status is None and exc.__cause__ is not None:
      message = _("The SMS could not be sent: could not connect to the SMS service. Try again later.")
    else:
      message = None
    if message:
      logger.warning("Error enviant la comunicació %s per SMS: %r", comm_id, exc)
      return message
  logger.error("Error desconegut enviant la comunicació %s per SMS", comm_id, exc_info=exc)
  return _("The SMS could not be sent. Unknown error from the SMS service.")
