from rest_framework import status
from rest_framework.decorators import action
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from statistics.models import DailyDocumentSubmissionStatus
from statistics.permissions import StatisticsPermission
from statistics.serializers import DailyDocumentSubmissionStatusSerializer


class DailyDocumentSubmissionStatusViewSet(viewsets.ModelViewSet):
    queryset = DailyDocumentSubmissionStatus.objects.all().order_by('position')
    serializer_class = DailyDocumentSubmissionStatusSerializer
    permission_classes = [IsAuthenticated, StatisticsPermission]

    @action(detail=False, methods=['post'], url_path='update-positions')
    def update_positions(self, request):
        updated_positions = []
        ids = request.data

        for new_position, id in enumerate(ids):
            instance = DailyDocumentSubmissionStatus.objects.filter(id=id).first()
            if instance:
                instance.position = new_position
                instance.save(update_fields=['position', 'updated_at'])
                updated_positions.append({
                    'id': instance.id,
                    'position': instance.position,
                    'name': instance.name,
                })

        return Response({
            "status": "positions updated",
            "updated": updated_positions
        }, status=status.HTTP_200_OK)
