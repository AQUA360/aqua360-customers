from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from ..models import OrderReason
from ..serializers.value_objects_serializer import OrderReasonSerializer
from order.permissions import OrderPermission
class OrderReasonViewSet(viewsets.ModelViewSet):
    queryset = OrderReason.objects.all().order_by('position')
    serializer_class = OrderReasonSerializer
    permission_classes = [IsAuthenticated, OrderPermission]
    search_fields = ['token', ]
    
    @action(detail=False, methods=['post'], url_path='update-positions')
    def update_positions(self, request):
        print("UPDATING POSITIONS")
        updated_positions = []
        ids = request.data

        for new_position, id in enumerate(ids):
            instance = OrderReason.objects.filter(id=id).first()
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