from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from statistics.models import DailyDocumentTemplate
from statistics.serializers import DailyDocumentTemplateSerializer, DailyDocumentTemplateListSerializer, DailyDocumentTemplateSaveSerializer
from statistics.permissions import StatisticsPermission


class DailyDocumentTemplateViewSet(viewsets.ModelViewSet):
    
    queryset = DailyDocumentTemplate.objects.all().order_by('-created_at')
    serializer_class = DailyDocumentTemplateSerializer
    permission_classes = [IsAuthenticated, StatisticsPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    ordering_fields = ['type', 'created_at', 'token', 'name']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return DailyDocumentTemplateListSerializer
        elif self.action == 'retrieve':
            return DailyDocumentTemplateSerializer
        return DailyDocumentTemplateSaveSerializer
    
    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()
