from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from statistics.models import ReadingBatchImportColumn, ReadingBatchImportTemplate
from statistics.permissions import StatisticsPermission
from statistics.serializers import (
    ReadingBatchImportColumnSerializer,
    ReadingBatchImportColumnSyncItemSerializer,
)


class ReadingBatchImportColumnViewSet(viewsets.ModelViewSet):
    queryset = ReadingBatchImportColumn.objects.all().order_by("id")
    serializer_class = ReadingBatchImportColumnSerializer
    permission_classes = [IsAuthenticated, StatisticsPermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        template_id = self.request.query_params.get("template")
        if template_id is not None:
            queryset = queryset.filter(template_id=template_id)
        return queryset

    def _resolve_template_id(self, request):
        template_id = request.query_params.get("template")
        if template_id is None and isinstance(request.data, dict):
            template_id = request.data.get("template")
        if template_id is None:
            return None, Response(
                {"detail": 'Query parameter "template" or body field "template" is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        get_object_or_404(ReadingBatchImportTemplate, pk=template_id)
        return template_id, None

    @action(detail=False, methods=["post"], url_path="sync")
    def sync(self, request):
        """
        Replace all columns for a template with the given list (atomic delete + bulk_create).
        Body: {"template": <id>, "columns": [{original_name, mapped_name}, ...]}
        or a JSON array with ?template=<id>.
        """
        template_id, error_response = self._resolve_template_id(request)
        if error_response is not None:
            return error_response

        raw = request.data
        if isinstance(raw, dict) and "columns" in raw:
            rows = raw["columns"]
            if not isinstance(rows, list):
                return Response(
                    {"detail": '"columns" must be a JSON array.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif isinstance(raw, list):
            rows = raw
        else:
            return Response(
                {
                    "detail": 'Expected {"template": <id>, "columns": [...]} or a JSON array with ?template=<id>.'
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        item_serializer = ReadingBatchImportColumnSyncItemSerializer(data=rows, many=True)
        item_serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            ReadingBatchImportColumn.objects.filter(template_id=template_id).delete()
            ReadingBatchImportColumn.objects.bulk_create(
                [
                    ReadingBatchImportColumn(template_id=template_id, **row)
                    for row in item_serializer.validated_data
                ]
            )

        refreshed = ReadingBatchImportColumn.objects.filter(template_id=template_id).order_by("id")
        return Response(
            ReadingBatchImportColumnSerializer(refreshed, many=True).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["delete", "post"], url_path="clear")
    def clear(self, request):
        """Remove all reading batch import column rows for a template."""
        template_id, error_response = self._resolve_template_id(request)
        if error_response is not None:
            return error_response

        with transaction.atomic():
            deleted_count, _ = ReadingBatchImportColumn.objects.filter(
                template_id=template_id
            ).delete()
        return Response(
            {"deleted": deleted_count},
            status=status.HTTP_200_OK,
        )
