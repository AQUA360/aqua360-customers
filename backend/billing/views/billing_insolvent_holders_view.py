import logging

from django.shortcuts import get_object_or_404
from rest_framework import status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from billing.models import Billing
from billing.permissions import BillingPermission
from billing.utils.insolvency_service import insolvent_holder_contracts
from billing.utils.terminated_contract_billing import _recalculation_readings, billable_readings

logger = logging.getLogger(__name__)


class BillingInsolventHoldersView(views.APIView):
    """Contractes de la facturació amb el titular insolvent: s'avisa l'usuari abans de processar
    (o, amb ?recalculate=1, de recalcular) la facturació. No n'exclou cap: és només un avís."""
    permission_classes = [IsAuthenticated, BillingPermission]
    queryset = Billing.objects.all()

    def get(self, request, id):
        from contract.models import Contract
        billing = get_object_or_404(Billing, id=id)
        recalculation = request.query_params.get('recalculate') in ('1', 'true', 'True')
        try:
            readings = _recalculation_readings(billing) if recalculation else billable_readings(billing)
            contracts = insolvent_holder_contracts(
                Contract.objects.filter(id__in=readings.values('contract_id'))
            ).order_by('token', 'id')
            results = [{
                'id': contract.id,
                'token': contract.token,
                'holder': str(contract.holder).strip() if contract.holder_id else None,
            } for contract in contracts]
        except Exception:
            logger.exception("No s'han pogut llistar els titulars insolvents de la facturació")
            return Response({"error": "Unexpected error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'results': results}, status=status.HTTP_200_OK)
