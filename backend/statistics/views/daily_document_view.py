from rest_framework.decorators import action
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from coredata.models import ConfigProject
from statistics.filters import DailyDocumentFilter
from statistics.models import DailyDocument
from statistics.serializers import DailyDocumentSerializer, DailyDocumentListSerializer
from statistics.permissions import StatisticsPermission
from statistics.tasks import regenerate_daily_document


class DailyDocumentViewSet(viewsets.ModelViewSet):
    
    queryset = DailyDocument.objects.all().order_by('-created_at')
    serializer_class = DailyDocumentSerializer
    permission_classes = [IsAuthenticated, StatisticsPermission]
    filterset_class = DailyDocumentFilter
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    ordering_fields = ['created_at', 'document_date', 'completed_at', 'cancelled_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return DailyDocumentListSerializer
        return DailyDocumentSerializer
    
    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()
    
    @action(detail=False, methods=['get'], url_path='pending')
    def return_pending_daily_documents(self, request):
        try:
            pending_status_token = ConfigProject.objects.get(token='daily_document_status_pending_token').value
            expired_status_token = ConfigProject.objects.get(token='daily_document_status_expired_token').value
            daily_documents = DailyDocument.objects.filter(status__token__in=[pending_status_token, expired_status_token])
            return Response(len(daily_documents), status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'], url_path='regenerate')
    def regenerate_daily_document(self, request, pk=None):
        try:
            daily_document = DailyDocument.objects.get(id=pk)
            if not daily_document or not daily_document.template:
                return Response({'error': 'Daily document not found'}, status=status.HTTP_404_NOT_FOUND)
            task = regenerate_daily_document.delay(daily_document.id)
            return Response({'task_id': task.id}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

