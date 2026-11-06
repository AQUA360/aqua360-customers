from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from service.permissions import ConnectionRequestPermission
from django_filters.rest_framework import DjangoFilterBackend

from service.models import ConnectionRequestBuildingType
from service.serializers.value_objects_serializer import ConnectionRequestBuildingTypeSerializer


class ConnectionRequestBuildingTypeViewSet(viewsets.ModelViewSet):
    queryset = ConnectionRequestBuildingType.objects.all().order_by('position', 'id')
    serializer_class = ConnectionRequestBuildingTypeSerializer
    filter_backends = (DjangoFilterBackend,)
    permission_classes = [IsAuthenticated, ConnectionRequestPermission]

    @action(detail=False, methods=['post'], url_path='update-positions')
    def update_positions(self, request):
        updated_positions = []
        ids = request.data

        for new_position, id in enumerate(ids):
            instance = ConnectionRequestBuildingType.objects.filter(id=id).first()
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
