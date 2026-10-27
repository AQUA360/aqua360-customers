import csv
from io import StringIO

from celery.result import AsyncResult
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import JsonResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from auth.permissions import PermissionManager
from billing.models import ReadingDocument
from billing.permissions import ReadingPermission
from billing.serializers.reading_document_serializer import (
    ReadingDocumentListSerializer,
    ReadingDocumentSerializer,
)
from billing.tasks import (
    import_smart_metering_document_task,
    preview_smart_metering_task,
    process_reading_document_file,
    validate_reading_document,
)
from billing.utils.reading_document_import_service import (
    ReadingDocumentPreviewValidationError,
    parse_reading_document_preview_params,
)
from billing.utils.smart_metering_service import (
    SMART_METERING_SCOPE_KEYS,
    _parse_request_date,
    find_smart_metering_documents,
    normalize_smart_metering_scope,
    smart_metering_document_is_replaceable,
    smart_metering_document_supply_point_ids,
    smart_metering_scope_options,
    smart_metering_scope_supply_point_ids,
)
from coredata.utils.name_utils import generate_token


class ReadingDocumentViewSet(viewsets.ModelViewSet):
    queryset = ReadingDocument.objects.all().order_by('-created_at')
    serializer_class = ReadingDocumentSerializer
    permission_classes = [IsAuthenticated, ReadingPermission]
    search_fields = ['token']
    ordering_fields = ['token']

    def get_serializer_class(self):
        if self.action == 'list':
            return ReadingDocumentListSerializer
        return ReadingDocumentSerializer

    def _auto_process_enabled(self):
        value = self.request.data.get('auto_process', True)
        if isinstance(value, str):
            return value.strip().lower() not in ('false', '0', 'no', 'off')
        return bool(value)

    def _celery_task_is_running(self, task_id):
        if not task_id:
            return False
        task_result = AsyncResult(task_id)
        return task_result.state in ['PENDING', 'STARTED', 'PROGRESS', 'RETRY']

    def _clear_stale_processing_lock(self, document):
        """If status is processing but Celery already finished/failed, unlock the document."""
        if document.status != ReadingDocument.STATUS_PROCESSING:
            return document
        if self._celery_task_is_running(document.task_id):
            return document

        task_state = AsyncResult(document.task_id).state if document.task_id else None
        if task_state == 'SUCCESS':
            document.status = ReadingDocument.STATUS_PROCESSED
            if not document.processed_at:
                from django.utils import timezone
                document.processed_at = timezone.now()
            document.save(update_fields=['status', 'processed_at'])
        else:
            # FAILURE / REVOKED / UNKNOWN / no task → allow process again
            document.status = ReadingDocument.STATUS_FAILED if task_state == 'FAILURE' else ReadingDocument.STATUS_PENDING
            document.save(update_fields=['status'])
        return document

    def _enqueue_process(self, document, *, reprocess=False):
        document = self._clear_stale_processing_lock(document)
        if self._celery_task_is_running(document.task_id):
            return document.task_id, True

        task = process_reading_document_file.delay(document.id, reprocess=reprocess)
        document.task_id = task.id
        document.status = ReadingDocument.STATUS_PROCESSING
        document.save(update_fields=['task_id', 'status'])
        return task.id, False

    def perform_create(self, serializer):
        instance = serializer.save()
        if self._auto_process_enabled():
            pass
            # self._enqueue_process(instance)
        else:
            instance.status = ReadingDocument.STATUS_PENDING
            instance.save(update_fields=['status'])

    def perform_update(self, serializer):
        instance = serializer.save()
        file_changed = 'file' in getattr(self.request, 'FILES', {})
        template_changed = 'template' in self.request.data
        if file_changed or template_changed:
            instance.last_preview = None
            if instance.status != ReadingDocument.STATUS_PROCESSING or not self._celery_task_is_running(instance.task_id):
                instance.status = ReadingDocument.STATUS_PENDING
                instance.processed_at = None
                instance.task_id = None
                instance.save(update_fields=['last_preview', 'status', 'processed_at', 'task_id'])
            else:
                instance.save(update_fields=['last_preview'])

    @action(detail=True, methods=['get', 'post'], url_path='validate')
    def validate_document(self, request, pk=None):
        document = self.get_object()
        if not document.file:
            return Response({"error": "El document no té fitxer."}, status=status.HTTP_400_BAD_REQUEST)
        if document.source == ReadingDocument.SOURCE_SMART_METERING:
            return self._smart_metering_not_processable()

        try:
            params = parse_reading_document_preview_params(
                query_params=request.query_params,
                data=request.data if request.method == 'POST' else None,
            )
        except ReadingDocumentPreviewValidationError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        task = validate_reading_document.delay(document.id, params)
        return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['post'], url_path='process')
    def process_document(self, request, pk=None):
        document = self._clear_stale_processing_lock(self.get_object())
        if not document.file:
            return Response({"error": "El document no té fitxer."}, status=status.HTTP_400_BAD_REQUEST)
        if document.source == ReadingDocument.SOURCE_SMART_METERING:
            return self._smart_metering_not_processable()
        if document.status == ReadingDocument.STATUS_PROCESSING and self._celery_task_is_running(document.task_id):
            return Response(
                {"task_id": document.task_id, "detail": "El document ja s'està processant."},
                status=status.HTTP_409_CONFLICT,
            )

        task_id, already_running = self._enqueue_process(document)
        if already_running:
            return Response(
                {"task_id": task_id, "detail": "El document ja s'està processant."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response({"task_id": task_id}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['post'], url_path='reprocess')
    def reprocess_document(self, request, pk=None):
        document = self._clear_stale_processing_lock(self.get_object())
        if not document.file:
            return Response({"error": "El document no té fitxer."}, status=status.HTTP_400_BAD_REQUEST)
        if document.source == ReadingDocument.SOURCE_SMART_METERING:
            return self._smart_metering_not_processable()
        if document.status == ReadingDocument.STATUS_PROCESSING and self._celery_task_is_running(document.task_id):
            return Response(
                {"task_id": document.task_id, "detail": "El document ja s'està processant."},
                status=status.HTTP_409_CONFLICT,
            )

        task_id, already_running = self._enqueue_process(document, reprocess=True)
        if already_running:
            return Response(
                {"task_id": task_id, "detail": "El document ja s'està processant."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response({"task_id": task_id}, status=status.HTTP_202_ACCEPTED)

    def _smart_metering_not_processable(self):
        return Response(
            {"error": "Les lectures de Smart Metering ja estan carregades; el document no es pot processar."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def _smart_metering_request_params(self, data):
        reading_date = data.get('reading_date')
        if not reading_date:
            raise ValueError("reading_date is required.")
        reading_date = _parse_request_date(reading_date)
        replace = data.get('replace')
        if isinstance(replace, str):
            replace = replace.strip().lower() in ('true', '1', 'yes', 'on')
        # Rutes, zones i lots: llistes al cos (POST) o separades per comes (GET).
        scope = data.get('scope')
        if not isinstance(scope, dict):
            scope = {
                key: [value for value in str(data.get(key) or '').split(',') if value]
                for key in SMART_METERING_SCOPE_KEYS
            }
        return reading_date, bool(replace), normalize_smart_metering_scope(scope)

    def _smart_metering_existing_document(self, reading_date, replace, scope):
        """
        Una sola càrrega de Smart Metering per data i comptador: es bloqueja si ja
        n'hi ha una de la data que comparteixi comptadors amb les rutes, zones o
        lots demanats. Només es pot substituir (``replace``) si és una sola, la nova
        selecció inclou tots els seus comptadors (si no, les lectures dels que en
        queden fora restarien al document), les seves lectures no s'han fet servir
        en cap lot ni factura i no s'està carregant.

        Retorna (document existent a substituir o None, resposta d'error o None).
        """
        overlapping = find_smart_metering_documents(reading_date, scope)
        if not overlapping:
            return None, None
        existing = self._clear_stale_processing_lock(overlapping[0])
        processing = (
            existing.status == ReadingDocument.STATUS_PROCESSING
            and self._celery_task_is_running(existing.task_id)
        )
        scope_reduced = not (
            smart_metering_document_supply_point_ids(existing)
            <= smart_metering_scope_supply_point_ids(scope)
        )
        replaceable = (
            len(overlapping) == 1
            and not processing
            and not scope_reduced
            and smart_metering_document_is_replaceable(existing)
        )
        if replace and replaceable:
            return existing, None
        return existing, Response(
            {
                "error": "Ja hi ha una càrrega de Smart Metering per a aquesta data.",
                "code": "smart_metering_document_exists",
                "existing_document": {
                    "id": existing.id,
                    "token": ", ".join(document.token or '' for document in overlapping),
                    "replaceable": replaceable,
                    "count": len(overlapping),
                    "scope_reduced": scope_reduced,
                    "processing": processing,
                },
            },
            status=status.HTTP_409_CONFLICT,
        )

    @action(detail=False, methods=['get'], url_path='smart-metering/preview')
    def smart_metering_preview(self, request):
        try:
            reading_date, replace, scope = self._smart_metering_request_params(request.query_params)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        _, conflict = self._smart_metering_existing_document(reading_date, replace, scope)
        if conflict:
            return conflict

        task = preview_smart_metering_task.delay(reading_date.isoformat(), scope)
        return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)

    @action(detail=False, methods=['get'], url_path='smart-metering/scope-options')
    def smart_metering_scope_options(self, request):
        """Rutes, zones i lots amb comptadors Smart Metering per triar què es carrega."""
        return Response(smart_metering_scope_options())

    @action(detail=False, methods=['post'], url_path='smart-metering/import')
    def smart_metering_import(self, request):
        try:
            reading_date, replace, scope = self._smart_metering_request_params(request.data)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        document, conflict = self._smart_metering_existing_document(reading_date, replace, scope)
        if conflict:
            return conflict

        if document is None:
            document = ReadingDocument.objects.create(
                token=generate_token(ReadingDocument),
                source=ReadingDocument.SOURCE_SMART_METERING,
                reading_date=reading_date,
                smart_metering_scope=scope,
                status=ReadingDocument.STATUS_PROCESSING,
            )
        else:
            document.status = ReadingDocument.STATUS_PROCESSING
            document.processed_at = None
            document.smart_metering_scope = scope
            document.save(update_fields=['status', 'processed_at', 'smart_metering_scope'])

        task = import_smart_metering_document_task.delay(document.id, request.data.get('preview'))
        document.task_id = task.id
        document.save(update_fields=['task_id'])
        return Response({"task_id": task.id, "document_id": document.id}, status=status.HTTP_202_ACCEPTED)

    @action(detail=False, methods=['get'], url_path='template')
    def get_template(self, request):
        from statistics.utils.report_service import delete_file_later

        titles = [
            "meter", "reading_value",
            "reading_date", "origin",
            "is_control", "leak_value",
            "observation"
        ]

        buffer = StringIO()
        writer = csv.writer(buffer, delimiter=';')
        writer.writerow(titles)
        file_bytes = buffer.getvalue().encode("utf-8")

        temp_rel_path = "tmp/EXTRA/readings_template.csv"
        saved_path = default_storage.save(temp_rel_path, ContentFile(file_bytes))
        file_url = request.build_absolute_uri(default_storage.url(saved_path))

        delete_file_later(saved_path, delay_seconds=20)

        return JsonResponse({"file_url": file_url}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='permissions')
    def permissions(self, request):
        pk = request.query_params.get('id')
        if pk:
            from django.contrib.auth.models import Group
            user_permissions = PermissionManager.get_model_permissions(request.user, 'auth', 'group')
            if not user_permissions['can_view'] or not user_permissions['can_change'] or not request.user.is_superuser:
                return Response(None, status=status.HTTP_403_FORBIDDEN)
            group = Group.objects.filter(id=pk).first()
            if not group:
                return Response(None, status=status.HTTP_404_NOT_FOUND)
            group_permissions = PermissionManager.get_model_group_permissions(group, 'readingdocument')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'readingdocument', 'billing')
        return Response(permissions, status=status.HTTP_200_OK)

    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()
