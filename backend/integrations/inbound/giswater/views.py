from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import (
    CONTRACTS_ENDPOINT,
    GiswaterInboundError,
    READINGS_ENDPOINT,
    fetch_contract_readings,
    fetch_contracts_export,
    log_inbound_request,
)


class GiswaterContractsView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    endpoint = CONTRACTS_ENDPOINT

    def get(self, request, *args, **kwargs):
        try:
            data = fetch_contracts_export(
                connection_token=request.query_params.get("connection_token"),
                connection_code_gis=request.query_params.get("connection_code_gis"),
            )
            log_inbound_request(
                endpoint=self.endpoint,
                method="GET",
                request_payload=request.query_params.dict(),
                response_payload={"count": len(data)},
                status_code=status.HTTP_200_OK,
                success=True,
                object_type="contract_export",
                object_id=str(request.user.pk),
            )
            return Response(data, status=status.HTTP_200_OK)
        except Exception as exc:
            log_inbound_request(
                endpoint=self.endpoint,
                method="GET",
                request_payload=request.query_params.dict(),
                response_payload={"detail": str(exc)},
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                error_message=str(exc),
                object_id=str(request.user.pk),
            )
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class GiswaterContractReadingsView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    endpoint = READINGS_ENDPOINT

    def get(self, request, contract_token, *args, **kwargs):
        endpoint = READINGS_ENDPOINT.format(contract_token=contract_token)
        request_payload = {"contract_token": contract_token, **request.query_params.dict()}

        try:
            data = fetch_contract_readings(contract_token)
            log_inbound_request(
                endpoint=endpoint,
                method="GET",
                request_payload=request_payload,
                response_payload={"count": len(data)},
                status_code=status.HTTP_200_OK,
                success=True,
                object_type="contract_readings",
                object_id=contract_token,
            )
            return Response(data, status=status.HTTP_200_OK)
        except GiswaterInboundError as exc:
            log_inbound_request(
                endpoint=endpoint,
                method="GET",
                request_payload=request_payload,
                response_payload={"detail": exc.detail},
                status_code=exc.status_code,
                success=False,
                error_message=exc.detail,
                object_type="contract_readings",
                object_id=contract_token,
            )
            return Response({"detail": exc.detail}, status=exc.status_code)
        except Exception as exc:
            log_inbound_request(
                endpoint=endpoint,
                method="GET",
                request_payload=request_payload,
                response_payload={"detail": str(exc)},
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                error_message=str(exc),
                object_type="contract_readings",
                object_id=contract_token,
            )
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
