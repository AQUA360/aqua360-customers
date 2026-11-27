from django.utils.translation import gettext
import hmac
import logging

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.inbound.signing.throttles import SigningCallbackThrottle
from integrations.inbound.signing.services import (
    EVENT_SIGNED,
    SigningCallbackError,
    handle_signing_callback,
    log_signing_callback,
)

logger = logging.getLogger(__name__)

NOT_AUTHORIZED = "No autoritzat."


def _api_key_is_valid(request):
    """
    La clau és obligatòria: sense `SIGN_CALLBACK_API_KEY` configurada el callback
    ho rebutja tot, perquè sense clau qualsevol podria marcar documents com a signats.
    La comparació és en temps constant per no donar pistes de la clau.
    """
    expected_key = getattr(settings, "SIGN_CALLBACK_API_KEY", "") or ""
    if not expected_key:
        return False
    received_key = request.headers.get("X-API-Key", "") or request.headers.get(
        "Aqua360-Api-Key", ""
    )
    return hmac.compare_digest(received_key.encode(), expected_key.encode())


class SigningCallbackView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = [SigningCallbackThrottle]

    def _reject(self, payload, detail, status_code, log_payload=True, persist=True):
        # Sense clau vàlida no s'escriu res a la BD: qualsevol persona d'Internet podria
        # fer créixer la taula de registres amb crides anònimes.
        if persist:
            log_signing_callback(
                payload if log_payload else {},
                success=False,
                status_code=status_code,
                error_message=detail,
                response_payload={"detail": detail},
            )
        return Response({"detail": detail}, status=status_code)

    def post(self, request, *args, **kwargs):
        payload = request.data
        is_dict = isinstance(payload, dict)

        if not _api_key_is_valid(request):
            if not getattr(settings, "SIGN_CALLBACK_API_KEY", ""):
                logger.warning(
                    "Callback de signatura rebutjat: SIGN_CALLBACK_API_KEY no està configurada."
                )
            return self._reject(payload, NOT_AUTHORIZED, status.HTTP_403_FORBIDDEN, persist=False)

        if not is_dict:
            return self._reject(
                payload, "Cos no vàlid.", status.HTTP_400_BAD_REQUEST, log_payload=False
            )

        # Aqua360 Sign només notifica les signatures; la caducitat la recull el sondeig.
        if payload.get("event") != EVENT_SIGNED:
            return self._reject(
                payload, "Esdeveniment no suportat.", status.HTTP_400_BAD_REQUEST
            )

        for field in ("external_reference", "session_id"):
            value = payload.get(field)
            if not isinstance(value, str) or not value.strip():
                return self._reject(
                    payload, f"{field} és obligatori.", status.HTTP_400_BAD_REQUEST
                )

        try:
            result = handle_signing_callback(payload)
            log_signing_callback(
                payload,
                success=True,
                status_code=status.HTTP_200_OK,
                response_payload=result,
            )
            return Response(result, status=status.HTTP_200_OK)
        except SigningCallbackError as exc:
            return self._reject(payload, str(exc.detail), exc.status_code)
        except Exception as exc:
            logger.exception("Error inesperat")
            log_signing_callback(
                payload,
                success=False,
                status_code=status.HTTP_400_BAD_REQUEST,
                error_message=str(exc),
                response_payload={"detail": str(exc)},
            )
            return Response({"detail": gettext("An unexpected error has occurred.")}, status=status.HTTP_400_BAD_REQUEST)
