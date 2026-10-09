from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import CONTRACTS_ENDPOINT, fetch_contracts_export, log_inbound_request


class SmartMeteringContractsView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    endpoint = CONTRACTS_ENDPOINT

    def get(self, request, *args, **kwargs):
        try:
            data = fetch_contracts_export(
                policy=request.query_params.get("policy"),
                meter=request.query_params.get("meter"),
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
