from celery.result import AsyncResult
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils.translation import gettext_lazy as _
from ..tasks import calculate_median_consumption, backfill_billing_consumption

class TriggerDailyConsumptionUpdate(APIView):
    """
    Endpoint per llançar manualment el càlcul de estadístiques de consum diari (ContractConsumption)
    sense esperar al procés automàtic mensual.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # Llançem la tasca de celery en segon pla
        task = calculate_median_consumption.delay()
        return Response(
            {
                "task_id": task.id,
                "message": _("S'ha iniciat el procés de recàlcul de consums diaris en segon pla.")
            },
            status=status.HTTP_202_ACCEPTED
        )

class TaskStatusView(APIView):
    """
    Retorna l'estat i el progrés d'una tasca Celery pel seu task_id.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id, *args, **kwargs):
        res = AsyncResult(task_id)

        if res.state == 'PROGRESS' and res.info:
            current = res.info.get('current', 0)
            total = res.info.get('total', 0)
            percent = float(res.info.get('percent', 0.0))
        elif res.state == 'SUCCESS':
            current = None
            total = None
            percent = 100.0
        else:
            current = 0
            total = 0
            percent = 0.0

        return Response({
            'task_id': task_id,
            'state': res.state,
            'current': current,
            'total': total,
            'percent': percent,
        })


class TriggerBillingConsumptionBackfill(APIView):
    """
    Endpoint per llançar el backfill de factures (BillingConsumption) que falten per processar.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # Llançem la tasca de celery en segon pla
        task = backfill_billing_consumption.delay()
        return Response(
            {
                "task_id": task.id,
                "message": _("S'ha iniciat el procés d'actualització de dades de facturació en segon pla.")
            },
            status=status.HTTP_202_ACCEPTED
        )
