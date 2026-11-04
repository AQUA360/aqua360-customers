import logging

from django.conf import settings
from django.db.models import Count, Max
from django.http import HttpResponse
from explorer.models import Query
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import CustomReportPermission
from ..serializers import CustomReportSerializer
from ..utils import custom_report_service as service

logger = logging.getLogger(__name__)


class CustomReportViewSet(viewsets.ModelViewSet):
    """Informes personalitzats: consultes SQL desades, executables i exportables.

    - CRUD: /statistics/custom-report/
    - POST /statistics/custom-report/{id}/run/      {params}            -> resultat
    - POST /statistics/custom-report/{id}/export/   {params, format}    -> fitxer csv/xlsx
    - POST /statistics/custom-report/run/           {sql, params}       -> SQL lliure (sense desar)
    - POST /statistics/custom-report/export/        {sql, params, format, title}
    - GET  /statistics/custom-report/schema/        -> taules i columnes consultables
    - GET  /statistics/custom-report/status/        -> configuració i permisos
    """

    serializer_class = CustomReportSerializer
    permission_classes = [CustomReportPermission]
    pagination_class = None
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering_fields = ['title', 'created_at', 'last_run_at', 'run_count']
    ordering = ['title']

    def get_queryset(self):
        return (
            Query.objects.select_related('created_by_user')
            .annotate(run_count=Count('querylog'), last_run_at=Max('querylog__run_at'))
        )

    def perform_create(self, serializer):
        serializer.save(created_by_user=self.request.user)

    # --- execució ---------------------------------------------------------------------------

    @staticmethod
    def _params(request):
        params = request.data.get('params') or {}
        return params if isinstance(params, dict) else {}

    @staticmethod
    def _error(exc):
        code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if isinstance(exc, service.CustomReportNotConfigured)
            else status.HTTP_400_BAD_REQUEST
        )
        # Errors esperats (SQL invàlid, error de PostgreSQL, sense configurar): sense traça.
        logger.info('Custom report request rejected: %s', exc.public_message)
        return Response({'error': exc.public_message}, status=code)

    def _run(self, request, sql, query=None):
        try:
            result = service.run_and_log(sql, self._params(request), user=request.user, query=query)
        except service.CustomReportError as exc:
            return self._error(exc)
        result['rows'] = service.to_json_rows(result['rows'])
        return Response(result)

    def _export(self, request, sql, title, query=None):
        file_format = (request.data.get('format') or 'xlsx').lower()
        if file_format not in service.EXPORT_FORMATS:
            return Response({'error': f'Unsupported format: {file_format}'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = service.run_and_log(
                sql, self._params(request), user=request.user, query=query,
                max_rows=settings.CUSTOM_REPORTS_EXPORT_MAX_ROWS,
            )
            content, content_type, filename = service.export(result, file_format, title)
        except service.CustomReportError as exc:
            return self._error(exc)
        response = HttpResponse(content, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['X-Truncated'] = 'true' if result['truncated'] else 'false'
        response['Access-Control-Expose-Headers'] = 'Content-Disposition, X-Truncated'
        return response

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        query = self.get_object()
        return self._run(request, query.sql, query=query)

    @action(detail=True, methods=['post'])
    def export(self, request, pk=None):
        query = self.get_object()
        return self._export(request, query.sql, query.title, query=query)

    @action(detail=False, methods=['post'], url_path='run')
    def run_sql(self, request):
        return self._run(request, request.data.get('sql'))

    @action(detail=False, methods=['post'], url_path='export')
    def export_sql(self, request):
        return self._export(request, request.data.get('sql'), request.data.get('title') or 'report')

    # --- suport a l'editor --------------------------------------------------------------------

    @action(detail=False, methods=['get'])
    def schema(self, request):
        try:
            return Response(service.get_schema())
        except service.CustomReportError as exc:
            return self._error(exc)

    @action(detail=False, methods=['get'])
    def status(self, request):
        return Response({
            'enabled': service.is_enabled(),
            'can_change': request.user.has_perm('explorer.change_query'),
            'max_rows': settings.CUSTOM_REPORTS_MAX_ROWS,
            'export_max_rows': settings.CUSTOM_REPORTS_EXPORT_MAX_ROWS,
            'statement_timeout': settings.CUSTOM_REPORTS_STATEMENT_TIMEOUT,
        })
