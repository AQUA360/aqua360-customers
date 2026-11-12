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
from statistics.utils.submission_service import (
    SubmissionError,
    submit_daily_document,
)
import logging

logger = logging.getLogger(__name__)


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

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action in ('retrieve', 'submit'):
            return qs.select_related(
                'status',
                'submission_status',
                'template',
                'template__available_report',
                'document',
                'completed_by',
                'cancelled_by',
            ).prefetch_related(
                'template__notify_users',
                'template__notify_groups',
            )
        if self.action == 'list':
            return qs.select_related(
                'status',
                'submission_status',
                'template',
                'completed_by',
                'cancelled_by',
                'document',
            )
        return qs
    
    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()
    
    @action(detail=False, methods=['get'], url_path='pending')
    def return_pending_daily_documents(self, request):
        try:
            from django.db.models import Q

            pending_status_token = ConfigProject.objects.get(token='daily_document_status_pending_token').value
            expired_status_token = ConfigProject.objects.get(token='daily_document_status_expired_token').value
            pending_count = DailyDocument.objects.filter(
                status__token__in=[pending_status_token, expired_status_token],
            ).count()
            # Submission errors only for templates that notify the current user
            # (directly or via one of their groups).
            user = request.user
            error_count = DailyDocument.objects.filter(
                submission_status__is_error=True,
                is_active=True,
            ).filter(
                Q(template__notify_users=user)
                | Q(template__notify_groups__in=user.groups.all())
            ).distinct().count()
            return Response(
                {'pending': pending_count, 'errors': error_count},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.exception("Error inesperat")
            return Response({'error': "Ha ocorregut un error inesperat."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'], url_path='regenerate')
    def regenerate_daily_document(self, request, pk=None):
        try:
            daily_document = DailyDocument.objects.get(id=pk)
            if not daily_document or not daily_document.template:
                return Response({'error': 'Daily document not found'}, status=status.HTTP_404_NOT_FOUND)
            task = regenerate_daily_document.delay(daily_document.id)
            return Response({'task_id': task.id}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("Error inesperat")
            return Response({'error': "Ha ocorregut un error inesperat."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='submit')
    def submit(self, request, pk=None):
        """Submit the daily document via its AvailableReport.submission_channel handler."""
        try:
            daily_document = self.get_object()
            result = submit_daily_document(daily_document, user=request.user)
            daily_document.refresh_from_db()
            payload = DailyDocumentSerializer(
                daily_document,
                context={'request': request},
            ).data
            payload['submission_result'] = result.to_api_dict()
            # Always 200 when the remote call was attempted and the result persisted;
            # the UI uses submission_result.ok / submission_status for success vs warnings.
            return Response(payload, status=status.HTTP_200_OK)
        except SubmissionError as e:
            logger.exception("Submission error while submitting daily document")
            return Response({'error': "No s'ha pogut completar l'enviament del document."}, status=e.status_code)
        except Exception:
            logger.exception("Error submitting daily document")
            return Response(
                {'error': "Ha ocorregut un error inesperat."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
