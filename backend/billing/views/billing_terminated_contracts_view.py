import logging

from django.shortcuts import get_object_or_404
from rest_framework import status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from billing.models import Billing
from billing.permissions import BillingPermission
from billing.utils.terminated_contract_billing import terminated_billable_contracts

logger = logging.getLogger(__name__)


class BillingTerminatedContractsView(views.APIView):
    """Contractes de baixa amb lectures per facturar: l'usuari tria quins es facturen
    abans de processar (o, amb ?recalculate=1, de recalcular) la facturació."""
    permission_classes = [IsAuthenticated, BillingPermission]
    queryset = Billing.objects.all()

    def get(self, request, id):
        billing = get_object_or_404(Billing, id=id)
        recalculation = request.query_params.get('recalculate') in ('1', 'true', 'True')
        try:
            contracts = (
                terminated_billable_contracts(billing, recalculation=recalculation)
                .select_related('holder')
                .order_by('token', 'id')
            )
            selected = set(billing.terminated_contract_ids_to_bill or [])
            results = [{
                'id': contract.id,
                'token': contract.token,
                'holder': str(contract.holder) if contract.holder_id else None,
                'termination_date': contract.termination_date,
                'selected': contract.id in selected,
            } for contract in contracts]
        except Exception:
            logger.exception("No s'han pogut llistar els contractes de baixa de la facturació")
            return Response({"error": "Unexpected error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'results': results}, status=status.HTTP_200_OK)
