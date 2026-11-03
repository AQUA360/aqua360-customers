from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from notification.models import IncidentChannel
from notification.permissions import IncidentPermission
from notification.serializers.value_objects_serializer import IncidentChannelSerializer


class ConfigListMixin:
    """Accions de les llistes de configuració (ordre i valor per defecte), com IncidentTypeViewSet."""

    @action(detail=False, methods=['post'], url_path='update-positions')
    def update_positions(self, request):
        model = self.queryset.model
        for new_position, item_id in enumerate(request.data):
            model.objects.filter(id=item_id).update(position=new_position)
        return Response({"status": "positions updated"}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='update-default')
    def update_default(self, request):
        model = self.queryset.model
        if not model.objects.filter(id=request.data).exists():
            return Response({"status": "error", "message": "No valid ID provided."}, status=status.HTTP_400_BAD_REQUEST)
        model.objects.update(is_default=False)
        model.objects.filter(id=request.data).update(is_default=True)
        return Response({"status": "is_default updated"}, status=status.HTTP_200_OK)


class IncidentChannelViewSet(ConfigListMixin, viewsets.ModelViewSet):
    queryset = IncidentChannel.objects.all().order_by('position')
    serializer_class = IncidentChannelSerializer
    permission_classes = [IsAuthenticated, IncidentPermission]
