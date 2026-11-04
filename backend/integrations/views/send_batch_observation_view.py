from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from integrations.filters.send_batch_observation_filter import SendBatchObservationFilter
from integrations.models import SendBatchObservation
from integrations.serializers.send_batch_serializer import SendBatchObservationSerializer


class SendBatchObservationViewSet(viewsets.ModelViewSet):
    queryset = SendBatchObservation.objects.filter(is_active=True).order_by("-created_at")
    serializer_class = SendBatchObservationSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = SendBatchObservationFilter
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def perform_create(self, serializer):
        send_batch = serializer.validated_data.get("send_batch")
        status_name = None
        status_obj = None
        if send_batch and send_batch.status:
            status_obj = send_batch.status
            status_name = send_batch.status.name
        serializer.save(
            user=self.request.user,
            status=status_obj,
            status_name=status_name,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
