from django.utils.translation import gettext as _
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from claimrequest.tasks import export_claim_contracts_task
from documentmanager.utils.export_jobs import enqueue_export, export_job_response
from documentmanager.utils.export_permissions import export_permission_class


class ClaimContractsExportSerializer(serializers.Serializer):
    contract_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    export_name = serializers.CharField(required=False, allow_blank=True)


class ClaimContractsExportView(APIView):
    """
    Exporta a Excel els contractes d'un llistat de gestió de reclamació (creació o
    qualsevol pas). Rep els ids des del frontal perquè en crear la gestió encara no
    existeix cap ClaimRequest. Va a la cua de descàrregues de l'usuari.
    """
    permission_classes = [IsAuthenticated, export_permission_class('claimrequest', 'claimrequest')]

    def post(self, request, *args, **kwargs):
        serializer = ClaimContractsExportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # dict.fromkeys: treu ids repetits i conserva l'ordre del llistat.
        contract_ids = list(dict.fromkeys(serializer.validated_data['contract_ids']))

        job = enqueue_export(
            request, export_claim_contracts_task, kind="claim_contracts",
            name=serializer.validated_data.get('export_name') or str(_("Contractes de la reclamació")),
            args=[contract_ids],
            params={"total": len(contract_ids)},
        )
        return Response(export_job_response(job), status=status.HTTP_202_ACCEPTED)
