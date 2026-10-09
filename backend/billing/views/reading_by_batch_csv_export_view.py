import datetime
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from billing.tasks import export_readings_by_batch_csv_task


class ReadingByBatchCSVExportView(APIView):
    """
    API endpoint that exports reading data by batch in CSV format.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        batch_id = request.query_params.get('batch')
        
        if not batch_id:
            return Response({"error": "El paràmetre 'batch' és obligatori"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Iniciar la tasca de Celery de manera asíncrona
            task = export_readings_by_batch_csv_task.delay(batch_id)
            
            return Response(
                {"task_id": task.id}, 
                status=status.HTTP_202_ACCEPTED
            )
            
        except Exception as e:
            return Response(
                {"error": f"Error intern del servidor: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )