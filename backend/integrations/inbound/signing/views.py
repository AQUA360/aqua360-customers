from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.inbound.signing.services import (
    SigningCallbackError,
    handle_signing_callback,
    log_signing_callback,
)


class SigningCallbackView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        payload = request.data
        # Autenticació opcional (vegeu customers-webhook-example.md): només es valida
        # si s'ha configurat una clau al nostre costat.
        expected_key = getattr(settings, "SIGN_CALLBACK_API_KEY", "")
        received_key = request.headers.get("X-API-Key", "") or request.headers.get(
            "Aqua360-Api-Key", ""
        )
        if expected_key and received_key != expected_key:
            log_signing_callback(
                payload,
                success=False,
                status_code=status.HTTP_403_FORBIDDEN,
                error_message="No autoritzat.",
                response_payload={"detail": "No autoritzat."},
            )
            return Response({"detail": "No autoritzat."}, status=status.HTTP_403_FORBIDDEN)

        if payload.get("event") not in ("session.signed", "session.expired"):
            log_signing_callback(
                payload,
                success=False,
                status_code=status.HTTP_400_BAD_REQUEST,
                error_message="Esdeveniment no suportat.",
                response_payload={"detail": "Esdeveniment no suportat."},
            )
            return Response(
                {"detail": "Esdeveniment no suportat."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        external_reference = (payload.get("external_reference") or "").strip()
        if not external_reference:
            log_signing_callback(
                payload,
                success=False,
                status_code=status.HTTP_400_BAD_REQUEST,
                error_message="external_reference és obligatori.",
                response_payload={"detail": "external_reference és obligatori."},
            )
            return Response(
                {"detail": "external_reference és obligatori."},
                status=status.HTTP_400_BAD_REQUEST,
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
            log_signing_callback(
                payload,
                success=False,
                status_code=exc.status_code,
                error_message=str(exc.detail),
                response_payload={"detail": exc.detail},
            )
            return Response({"detail": exc.detail}, status=exc.status_code)
        except Exception as exc:
            log_signing_callback(
                payload,
                success=False,
                status_code=status.HTTP_400_BAD_REQUEST,
                error_message=str(exc),
                response_payload={"detail": str(exc)},
            )
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
