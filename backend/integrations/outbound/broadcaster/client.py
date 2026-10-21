import requests
from django.conf import settings

from coredata.utils.phone_utils import to_broadcaster_format
from integrations.models import IntegrationRequestLog

from .exceptions import BroadcasterError

PROVIDER = "broadcaster"

# Broadcaster és darrere Cloudflare: sense capçaleres de navegador les crides
# servidor-a-servidor poden rebre un 403 per detecció de bot (com a Aqua360 Sign).
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Variable de la plantilla amb el text ja resolt de cada destinatari.
MESSAGE_VARIABLE = "message"


class BroadcasterClient:
    def __init__(self, api_url=None, api_token=None, timeout=None):
        self.api_url = api_url or settings.BROADCASTER_API_URL
        self.api_token = api_token or settings.BROADCASTER_API_TOKEN
        self.timeout = timeout or settings.BROADCASTER_TIMEOUT_SECONDS

    def _get_headers(self):
        return {
            "User-Agent": settings.BROADCASTER_USER_AGENT or DEFAULT_USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "ca-ES,ca;q=0.9,en;q=0.8",
            "Authorization": f"Token {self.api_token}",
            "Content-Type": "application/json",
        }

    def _log_request(self, *, status_code=None, success=False, error_message="", object_type="", object_id=""):
        # Sense el payload: porta telèfons i text dels missatges, que són dades personals.
        IntegrationRequestLog.objects.create(
            provider=PROVIDER,
            direction=IntegrationRequestLog.DIRECTION_OUTBOUND,
            method="POST",
            endpoint=self.api_url,
            request_payload={},
            status_code=status_code,
            success=success,
            error_message=error_message,
            object_type=object_type,
            object_id=object_id,
        )

    def send_sms(self, *, recipient_name, phones, text, object_type="", object_id=""):
        """
        Envia el mateix SMS a tots els telèfons, amb el payload que fa servir Aqua360 Sign.

        El text ja ve resolt (sense variables %...): la plantilla de Broadcaster
        només el rep per context.
        """
        if not self.api_url or not self.api_token:
            raise BroadcasterError("BROADCASTER_API_URL i BROADCASTER_API_TOKEN no estan configurats.")
        if not text:
            raise BroadcasterError("L'SMS no té text.")

        recipients = []
        for phone in phones:
            value = to_broadcaster_format(phone)
            if not value:
                raise BroadcasterError(f"El telèfon {phone} no pot rebre SMS.")
            recipients.append({
                "name": recipient_name or "",
                "value": value,
                "context": {MESSAGE_VARIABLE: text},
            })
        if not recipients:
            raise BroadcasterError("No hi ha cap telèfon per enviar l'SMS.")

        payload = {
            "channel": settings.BROADCASTER_CHANNEL,
            "topic": settings.BROADCASTER_TOPIC,
            "template": {
                "code": settings.BROADCASTER_TEMPLATE_CODE,
                "name": settings.BROADCASTER_TEMPLATE_NAME,
                "template_type": "text",
                "subject": settings.BROADCASTER_TEMPLATE_NAME,
                "body": settings.BROADCASTER_TEMPLATE_BODY,
                "available_variables": [MESSAGE_VARIABLE],
            },
            "recipients": recipients,
        }

        try:
            response = requests.post(self.api_url, json=payload, headers=self._get_headers(), timeout=self.timeout)
        except requests.RequestException as exc:
            error_message = f"Error connectant amb Broadcaster: {exc}"
            self._log_request(error_message=error_message, object_type=object_type, object_id=object_id)
            raise BroadcasterError(error_message) from exc

        if response.status_code >= 400:
            error_message = f"Error resposta Broadcaster {response.status_code}: {response.text[:500]}"
            self._log_request(
                status_code=response.status_code, error_message=error_message,
                object_type=object_type, object_id=object_id,
            )
            raise BroadcasterError(error_message)

        self._log_request(
            status_code=response.status_code, success=True, object_type=object_type, object_id=object_id,
        )
