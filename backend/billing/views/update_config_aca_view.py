from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.permissions import BillingPermission
from billing.utils.update_config_aca_service import update_config_aca_service


class UpdateConfigAcaView(APIView):
    permission_classes = [IsAuthenticated, BillingPermission]

    def post(self, request, *args, **kwargs):
        update_config_aca_service()
        return Response({'status': 'ok'}, status=status.HTTP_200_OK)
