from celery.result import AsyncResult
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from claimrequest.models import ClaimRequest, ClaimRequestPayment
from claimrequest.tasks import export_claim_contracts_task
from documentmanager.utils.export_jobs import enqueue_export, export_job_response
from documentmanager.utils.export_permissions import export_permission_class


class ClaimContractsExportSerializer(serializers.Serializer):
    contract_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    export_name = serializers.CharField(required=False, allow_blank=True)
    # Abast del llistat: la gestió ja creada o, en crear-la, la tasca de filtratge (obtain_claim_request_data).
    claim_request_id = serializers.IntegerField(required=False)
    filter_task_id = serializers.CharField(required=False)
    # Pagaments que l'usuari ha tret del llistat (en crear la gestió): surten marcats com a exclosos.
    exclude_payment_ids = serializers.ListField(child=serializers.IntegerField(), required=False)

    def validate(self, attrs):
        if bool(attrs.get('claim_request_id')) == bool(attrs.get('filter_task_id')):
            raise serializers.ValidationError(_("Cal indicar la gestió de reclamació o la tasca de filtratge."))
        return attrs


def _scope_payments_by_contract(validated_data):
    """
    Pagaments reclamats per contracte dins l'abast del llistat, com a parelles
    (payment_id, exclòs), calculats al servidor (no es confia en la selecció del
    frontal). Les claus són els contractes que es poden exportar.
    """
    claim_request_id = validated_data.get('claim_request_id')
    if claim_request_id:
        claim_request = get_object_or_404(ClaimRequest, id=claim_request_id)
        payments_by_contract = {}
        rows = ClaimRequestPayment.objects.filter(
            claim_request=claim_request, contract__isnull=False,
        ).values_list('contract_id', 'payment_id', 'is_excluded').order_by('id')
        for contract_id, payment_id, is_excluded in rows:
            contract_payments = payments_by_contract.setdefault(contract_id, [])
            if payment_id:
                contract_payments.append((payment_id, is_excluded))
        return payments_by_contract

    task_result = AsyncResult(validated_data['filter_task_id'])
    result = task_result.result if task_result.state == 'SUCCESS' else None
    if not isinstance(result, dict) or not isinstance(result.get('contracts'), list):
        return None
    return {
        contract.get('id'): [
            (payment.get('id'), False) for payment in contract.get('payments') or []
            if isinstance(payment, dict) and payment.get('id')
        ]
        for contract in result['contracts'] if isinstance(contract, dict)
    }


class ClaimContractsExportView(APIView):
    """
    Exporta a Excel els contractes d'un llistat de gestió de reclamació (creació o
    qualsevol pas) i el detall de les factures reclamades de cada contracte. Rep els
    ids des del frontal perquè en crear la gestió encara no existeix cap ClaimRequest;
    només s'accepten els que pertanyen a l'abast indicat.
    Va a la cua de descàrregues de l'usuari.
    """
    permission_classes = [IsAuthenticated, export_permission_class('claimrequest', 'claimrequest')]

    def post(self, request, *args, **kwargs):
        serializer = ClaimContractsExportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # dict.fromkeys: treu ids repetits i conserva l'ordre del llistat.
        contract_ids = list(dict.fromkeys(serializer.validated_data['contract_ids']))

        payments_by_contract = _scope_payments_by_contract(serializer.validated_data)
        if payments_by_contract is None:
            return Response(
                {"error": _("La tasca de filtratge no existeix o encara no ha acabat.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not set(contract_ids) <= payments_by_contract.keys():
            return Response(
                {"error": _("Hi ha contractes que no pertanyen a aquesta gestió de reclamació.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        exclude_payment_ids = set(serializer.validated_data.get('exclude_payment_ids') or [])
        job = enqueue_export(
            request, export_claim_contracts_task, kind="claim_contracts",
            name=serializer.validated_data.get('export_name') or str(_("Contractes de la reclamació")),
            args=[contract_ids, [
                [contract_id, payment_id, is_excluded or payment_id in exclude_payment_ids]
                for contract_id in contract_ids
                for payment_id, is_excluded in payments_by_contract[contract_id]
            ]],
            params={"total": len(contract_ids)},
        )
        return Response(export_job_response(job), status=status.HTTP_202_ACCEPTED)
