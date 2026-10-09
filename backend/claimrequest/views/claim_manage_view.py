from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from celery.result import AsyncResult
from django.http import QueryDict
from claimrequest.tasks import obtain_claim_request_data
from ..models import ClaimRequest, ClaimRequestPayment
from ..serializers.claim_request_save_serializer import ExcludeContractSerializer


class ClaimManageViewSet(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = ClaimRequest.objects.all().order_by('-created_at')

    def post(self, request, *args, **kwargs):
        if isinstance(request.data, QueryDict):
            payload = {
                key: request.data.getlist(key)
                if len(request.data.getlist(key)) > 1
                else request.data.get(key)
                for key in request.data
            }
        else:
            payload = dict(request.data)
        task = obtain_claim_request_data.delay(payload)
        return Response({
            "task_id": task.id,
            "status": "pending",
            "message": "Obtenint dades de reclamació. Utilitza el task_id per comprovar l'estat.",
        }, status=status.HTTP_202_ACCEPTED)

    def get(self, request, *args, **kwargs):
        task_id = request.query_params.get('task_id')
        if not task_id:
            return Response(
                {"error": "Cal proporcionar el paràmetre task_id"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task_result = AsyncResult(task_id)
        if task_result.state == 'FAILURE':
            return Response({
                'status': task_result.state,
                'error': str(task_result.info),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        if task_result.state == 'SUCCESS':
            return Response({
                'status': task_result.state,
                **task_result.result,
            })
        return Response({
            'status': task_result.state,
            'task_id': task_id,
        })


# Vista per excloure contractes d'una reclamació
# Permet marcar com exclosos tots els pagaments associats a un contracte específic dins d'una reclamació
# També registra un log de l'acció realitzada per mantenir un històric dels canvis

class ExcludeContractViewSet(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = ClaimRequest.objects.all().order_by('-created_at')

    def get(self, request, *args, **kwargs):
        return Response({"message": "Aquesta vista només accepta mètodes POST"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def post(self, request, *args, **kwargs):
        serializer = ExcludeContractSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        request_id = serializer.validated_data['request_id']
        contract_id = serializer.validated_data['contract_id']
        
        try:
            claim_request = ClaimRequest.objects.get(id=request_id)
            
            # Obtenim els ClaimRequestPayment que tenen el contracte especificat
            claim_payments = ClaimRequestPayment.objects.filter(
                claim_request=claim_request,
                contract__id=contract_id
            )
            
            # Actualitzem el camp is_excluded a True
            updated_count = claim_payments.update(is_excluded=True)
            
            # Creem un log de l'acció
            from order.middleware import get_current_user
            user = get_current_user()
            from logger.models import LogClaimRequestContractChange
            LogClaimRequestContractChange.objects.create(
                object=claim_request,
                deleted_contract=claim_payments.first().contract if claim_payments.exists() else None,
                user=user,
            )
            
            return Response({
                "message": f"S'han exclòs {updated_count} pagaments del contracte",
                "updated_count": updated_count
            })
            
        except ClaimRequest.DoesNotExist:
            return Response(
                {"error": "La reclamació no existeix"},
                status=status.HTTP_404_NOT_FOUND
            )
