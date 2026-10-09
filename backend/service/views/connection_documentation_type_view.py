from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend

from service.models import ConnectionDocumentationType
from service.serializers.value_objects_serializer import ConnectionDocumentationTypeSerializer


class ConnectionDocumentationTypeViewSet(viewsets.ModelViewSet):
    queryset = ConnectionDocumentationType.objects.all().order_by('position')
    serializer_class = ConnectionDocumentationTypeSerializer
    filter_backends = (DjangoFilterBackend,)
    permission_classes = [IsAuthenticated, DjangoModelPermissions]

    @action(detail=False, methods=['post'], url_path='update-positions')
    def update_positions(self, request):
        updated_positions = []
        ids = request.data

        for new_position, id in enumerate(ids):
            instance = ConnectionDocumentationType.objects.filter(id=id).first()
            if instance:
                instance.position = new_position
                instance.save()
                updated_positions.append({
                    'id': instance.id,
                    'position': instance.position,
                    'name': instance.name,
                    'is_default': instance.is_default
                })

        return Response({
            "status": "positions updated",
            "updated": updated_positions
        }, status=status.HTTP_200_OK)
