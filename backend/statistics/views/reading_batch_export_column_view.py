from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from statistics.models import ReadingBatchExportColumn
from statistics.serializers import (
    ReadingBatchExportColumnSerializer,
    ReadingBatchExportColumnSyncItemSerializer,
)
from statistics.permissions import StatisticsPermission


class ReadingBatchExportColumnViewSet(viewsets.ModelViewSet):
    queryset = ReadingBatchExportColumn.objects.all().order_by("position", "id")
    serializer_class = ReadingBatchExportColumnSerializer
    permission_classes = [IsAuthenticated, StatisticsPermission]

    @action(detail=False, methods=["post"], url_path="sync")
    def sync(self, request):
        """
        Replace all rows with the given list (atomic delete + bulk_create).
        Body: a JSON array of objects {name, value, position}, or {"columns": [...]}.
        """
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
                    "detail": "Expected a JSON array [...] or an object {\"columns\": [...]}."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        item_serializer = ReadingBatchExportColumnSyncItemSerializer(data=rows, many=True)
        item_serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            ReadingBatchExportColumn.objects.all().delete()
            ReadingBatchExportColumn.objects.bulk_create(
                [ReadingBatchExportColumn(**row) for row in item_serializer.validated_data]
            )

        refreshed = ReadingBatchExportColumn.objects.all().order_by("position", "id")
        return Response(
            ReadingBatchExportColumnSerializer(refreshed, many=True).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["delete", "post"], url_path="clear")
    def clear(self, request):
        """Remove all reading batch export column rows."""
        with transaction.atomic():
            deleted_count, _ = ReadingBatchExportColumn.objects.all().delete()
        return Response(
            {"deleted": deleted_count},
            status=status.HTTP_200_OK,
        )
