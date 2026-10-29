import logging

from django.http import HttpResponse
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from auth.permissions import PermissionManager
from billing.utils.smart_metering_service import (
    build_smart_metering_openapi,
    build_smart_metering_server_curl,
    get_smart_metering_settings,
    probe_smart_metering_connectivity,
    probe_smart_metering_readings,
)

logger = logging.getLogger(__name__)

_DATE_ERROR_CODES = {"reading_date_required", "reading_date_invalid"}


def _attachment(content, filename, content_type):
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "no-store"
    return response


class SmartMeteringSettingsView(APIView):
    """
    Smart Metering connection settings and connectivity probes.

    GET returns the API URL (env) and the ConfigProject authentication token.
    POST action ``connectivity`` checks that the host answers.
    POST action ``readings`` returns a sample of one day's readings and does not
    save them.
    """

    permission_classes = [IsAuthenticated]

    def _check_permission(self, request):
        if not PermissionManager.has_permission(request.user, "view_user"):
            raise PermissionDenied("You don't have permission to view Smart Metering settings.")

    def get(self, request):
        self._check_permission(request)
        download = request.query_params.get("download")
        if not download:
            return Response(get_smart_metering_settings())
        try:
            if download == "openapi":
                connection = get_smart_metering_settings()
                server_url = request.build_absolute_uri("/").rstrip("/")
                if str(connection.get("inbound_endpoint") or "").startswith("/api/"):
                    server_url += "/api"
                content = build_smart_metering_openapi(server_url)
                return _attachment(content, "openapi.yaml", "application/yaml; charset=utf-8")
            if download == "curl":
                content = build_smart_metering_server_curl(
                    request.query_params.get("reading_date"),
                    meter_code=request.query_params.get("meter"),
                )
                return _attachment(content, "smartmetering-curl.sh", "text/x-shellscript; charset=utf-8")
        except ValueError as exc:
            allowed_codes = {
                "not_configured",
                "url_missing",
                "reading_date_required",
                "reading_date_invalid",
                "server_url_invalid",
                "openapi_template_invalid",
            }
            raw_code = exc.args[0] if exc.args else None
            code = raw_code if raw_code in allowed_codes else "reading_date_invalid"
            return Response({"code": code}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Error inesperat en descarregar la prova de Smart Metering")
            return Response({"code": "unexpected_error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"code": "download_invalid"}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        self._check_permission(request)
        payload = request.data if isinstance(request.data, dict) else {}
        action = payload.get("action")
        try:
            if action == "connectivity":
                return Response(probe_smart_metering_connectivity())
            if action == "readings":
                return Response(
                    probe_smart_metering_readings(
                        payload.get("reading_date"),
                        meter_code=payload.get("meter"),
                    )
                )
        except ValueError as exc:
            code = str(exc)
            if code not in _DATE_ERROR_CODES:
                code = "reading_date_invalid"
            return Response({"code": code}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Error inesperat en la prova de Smart Metering")
            return Response({"code": "unexpected_error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"code": "action_invalid"}, status=status.HTTP_400_BAD_REQUEST)
