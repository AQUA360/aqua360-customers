from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from statistics.models import ReadingBatchImportTemplate
from statistics.permissions import StatisticsPermission
from statistics.serializers import ReadingBatchImportTemplateSerializer


class ReadingBatchImportTemplateViewSet(viewsets.ModelViewSet):
    queryset = ReadingBatchImportTemplate.objects.all().order_by("name", "id")
    serializer_class = ReadingBatchImportTemplateSerializer
    permission_classes = [IsAuthenticated, StatisticsPermission]
