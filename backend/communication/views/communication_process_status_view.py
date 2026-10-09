from rest_framework import viewsets,status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response

from communication.models import CommunicationProcessStatus
from communication.serializers.value_objects_serializer import CommunicationProcessStatusSerializer
from communication.permissions import CommunicationPermission
class CommunicationProcessStatusViewSet(viewsets.ModelViewSet):
    queryset = CommunicationProcessStatus.objects.all().order_by('position')
    serializer_class = CommunicationProcessStatusSerializer
    permission_classes = [IsAuthenticated, CommunicationPermission]
    
    @action(detail=False, methods=['post'], url_path='update-positions')
    def update_positions(self, request):
        updated_positions = []
        ids = request.data

        for new_position, id in enumerate(ids):
            instance = CommunicationProcessStatus.objects.filter(id=id).first()
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
    
    @action(detail=False, methods=['post'], url_path='update-default')
    def update_default(self, request):
        updated_items = []
        id = request.data

        # Validar que el ID existeix
        if not CommunicationProcessStatus.objects.filter(id=id).exists():
            return Response({
                "status": "error",
                "message": "No valid ID provided."
            }, status=status.HTTP_400_BAD_BAD_REQUEST)

        # Marcar tots els ids com a no default
        CommunicationProcessStatus.objects.update(is_default=False)

        # Després marcar el que toca com a default
        default_item = CommunicationProcessStatus.objects.get(id=id)
        default_item.is_default = True
        default_item.save()
        updated_items.append({
            'id': default_item.id,
            'is_default': default_item.is_default
        })

        return Response({
            "status": "is_default updated",
            "updated": updated_items
        }, status=status.HTTP_200_OK)