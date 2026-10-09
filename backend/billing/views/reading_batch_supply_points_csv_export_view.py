from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from billing.tasks import export_reading_batch_supply_points_csv_task


class ReadingBatchSupplyPointsCSVExportView(APIView):
    """
    Exporta en CSV els SupplyPoints de les Routes d'un ReadingBatch,
    amb la lectura del lot associada (si n'hi ha) i els contractes.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        batch_id = request.query_params.get('batch')

        if not batch_id:
            return Response(
                {"error": "El paràmetre 'batch' és obligatori"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            task = export_reading_batch_supply_points_csv_task.delay(batch_id)
            return Response(
                {"task_id": task.id},
                status=status.HTTP_202_ACCEPTED,
            )
        except Exception as e:
            return Response(
                {"error": f"Error intern del servidor: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
