import csv
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from django.db.models import Subquery, OuterRef, Max, Prefetch

from service.models import Meter, SupplyPoint
from billing.models import Reading


class MeterExportViewSet(viewsets.ViewSet):
    """
    ViewSet per exportar comptadors en CSV amb la seva última lectura.
    """
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Meter.objects.all()
    
    def get_queryset(self):
        """
        Retorna el queryset de comptadors per als permisos.
        """
        return Meter.objects.filter(is_active=True)

    @action(detail=False, methods=['get'], url_path='csv')
    def export_csv(self, request):
        """
        Inicia la generació asíncrona de l'exportació de comptadors en CSV.
        """
        try:
            status_param = request.query_params.get('status', None)
            ordering_param = request.query_params.get('ordering', 'code')
            exploitation_param = request.query_params.get('exploitation', None)
            
            # Execució de la tasca de Celery de manera asíncrona
            from service.tasks import export_meters_csv_task
            task = export_meters_csv_task.delay(
                status_param=status_param,
                ordering_param=ordering_param,
                exploitation_param=exploitation_param
            )
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Generació de l'exportació de comptadors iniciada correctament. Utilitza el task_id per comprovar l'estat."
            }, status=status.HTTP_202_ACCEPTED)
            
        except Exception as e:
            return Response(
                {"error": f"Error en iniciar l'exportació: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

