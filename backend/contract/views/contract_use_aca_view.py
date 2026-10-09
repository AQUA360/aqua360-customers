from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from contract.tasks import fill_contract_use_aca_task
from contract.utils.use_aca_service import get_use_aca_stats, run_fill_contract_use_aca


class ContractUseAcaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.has_perm('contract.view_contract'):
            return Response(status=status.HTTP_403_FORBIDDEN)

        return Response(get_use_aca_stats(), status=status.HTTP_200_OK)

    def post(self, request):
        if not request.user.has_perm('contract.change_contract'):
            return Response(status=status.HTTP_403_FORBIDDEN)

        dry_run = bool(request.data.get('dry_run', False))
        update_all_contracts = bool(request.data.get('update_all_contracts', False))
        run_async = bool(request.data.get('async', not dry_run))

        if run_async and not dry_run:
            task = fill_contract_use_aca_task.delay(
                update_all_contracts=update_all_contracts,
            )
            return Response(
                {
                    'status': 'pending',
                    'task_id': task.id,
                    'message': (
                        "Ompliment de use_aca iniciat en segon pla. "
                        "Utilitza el task_id per comprovar l'estat."
                    ),
                },
                status=status.HTTP_202_ACCEPTED,
            )

        result = run_fill_contract_use_aca(
            update_all_contracts=update_all_contracts,
            dry_run=dry_run,
        )
        return Response(result, status=status.HTTP_200_OK)
