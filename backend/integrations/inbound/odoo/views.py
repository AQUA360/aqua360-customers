import logging

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.inbound.odoo.services import (
    OdooBatchCallbackError,
    apply_odoo_batch_result,
    log_odoo_batch_callback,
)

logger = logging.getLogger(__name__)


class OdooBatchResultView(APIView):
    """
    Inbound: Odoo envia el resultat final d'un lot quan status=done.

    Autenticació: Authorization: Bearer <ODOO_INBOUND_BEARER_TOKEN>
    Cos: mateix JSON que GET /aqua360/batch/{batch_id}.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        payload = request.data if isinstance(request.data, dict) else {}
        batch_id = (payload.get("batch_id") or "").strip()

        expected = getattr(settings, "ODOO_INBOUND_BEARER_TOKEN", "") or ""
        auth_header = request.headers.get("Authorization", "") or ""
        received = ""
        if auth_header.lower().startswith("bearer "):
            received = auth_header[7:].strip()

        if not expected or received != expected:
            log_odoo_batch_callback(
                payload,
                success=False,
                status_code=status.HTTP_401_UNAUTHORIZED,
                error_message="UNAUTHORIZED",
                response_payload={"detail": "UNAUTHORIZED"},
                object_id=batch_id,
            )
            return Response(
                {"detail": "UNAUTHORIZED"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            result = apply_odoo_batch_result(payload)
            log_odoo_batch_callback(
                payload,
                success=True,
                status_code=status.HTTP_200_OK,
                response_payload=result,
                object_id=batch_id,
            )
            return Response(result, status=status.HTTP_200_OK)
        except OdooBatchCallbackError as exc:
            log_odoo_batch_callback(
                payload,
                success=False,
                status_code=exc.status_code,
                error_message=str(exc.detail),
                response_payload={"detail": exc.detail},
                object_id=batch_id,
            )
            return Response({"detail": exc.detail}, status=exc.status_code)
        except Exception as exc:
            logger.exception("Unexpected error in Odoo batch inbound")
            log_odoo_batch_callback(
                payload,
                success=False,
                status_code=status.HTTP_400_BAD_REQUEST,
                error_message=str(exc),
                response_payload={"detail": "An unexpected error occurred."},
                object_id=batch_id,
            )
            return Response(
                {"detail": "An unexpected error occurred."},
                status=status.HTTP_400_BAD_REQUEST,
            )
