from rest_framework import viewsets,status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions


from contract.models import (VariableType)
from contract.serializers.value_objects_serializer import (VariableTypeSerializer)
from contract.permissions import ContractPermission
class VariableTypeViewSet(viewsets.ModelViewSet):
    queryset = VariableType.objects.all().order_by('position')
    serializer_class = VariableTypeSerializer
    permission_classes = [IsAuthenticated, ContractPermission]
    
    @action(detail=False, methods=['post'], url_path='update-positions')
    def update_positions(self, request):
        updated_positions = []
        ids = request.data

        for new_position, id in enumerate(ids):
            instance = VariableType.objects.filter(id=id).first()
            if instance:
                instance.position = new_position
                instance.save()
                updated_positions.append({
                    'id': instance.id,
                    'position': instance.position,
                    'name': instance.name
                })

        return Response({
            "status": "positions updated",
            "updated": updated_positions
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], url_path='all')
    def all(self, request):
        self.pagination_class = None
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response(serializer.data)