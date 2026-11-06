from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.models import SendBatchProvider, SendBatchStatus, SendBatchType
from integrations.serializers.send_batch_serializer import (
    SendBatchProviderSerializer,
    SendBatchStatusSerializer,
    SendBatchTypeSerializer,
)
from integrations.utils.send_batch_defaults import (
    ensure_send_batch_defaults,
    get_send_batch_settings_overview,
)


class _CatalogMixin:
    """Accions compartides amb ConfigList (posicions i valor per defecte)."""

    default_scope_field = None

    @action(detail=False, methods=["post"], url_path="update-positions")
    def update_positions(self, request):
        updated_positions = []
        ids = request.data

        for new_position, item_id in enumerate(ids):
            instance = self.get_queryset().filter(id=item_id).first()
            if instance:
                instance.position = new_position
                instance.save(update_fields=["position", "updated_at"])
                updated_positions.append(
                    {
                        "id": instance.id,
                        "position": instance.position,
                        "name": instance.name,
                        "is_default": instance.is_default,
                    }
                )

        return Response(
            {"status": "positions updated", "updated": updated_positions},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="update-default")
    def update_default(self, request):
        item_id = request.data
        instance = self.get_queryset().filter(id=item_id).first()
        if not instance:
            return Response(
                {"status": "error", "message": "No valid ID provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = self.get_queryset()
        scope_field = getattr(self, "default_scope_field", None)
        if scope_field:
            qs = qs.filter(**{scope_field: getattr(instance, scope_field)})
        qs.update(is_default=False)

        instance.is_default = True
        instance.save(update_fields=["is_default", "updated_at"])

        return Response(
            {
                "status": "is_default updated",
                "updated": [{"id": instance.id, "is_default": instance.is_default}],
            },
            status=status.HTTP_200_OK,
        )


class SendBatchProviderViewSet(_CatalogMixin, viewsets.ModelViewSet):
    queryset = SendBatchProvider.objects.all().order_by("position", "token", "id")
    serializer_class = SendBatchProviderSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None


class SendBatchTypeViewSet(_CatalogMixin, viewsets.ModelViewSet):
    queryset = SendBatchType.objects.select_related("provider").order_by(
        "provider__position", "position", "token", "id"
    )
    serializer_class = SendBatchTypeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    default_scope_field = "provider_id"

    def get_queryset(self):
        qs = super().get_queryset()
        provider = self.request.query_params.get("provider")
        if provider:
            qs = qs.filter(provider_id=provider)
        return qs


class SendBatchStatusViewSet(_CatalogMixin, viewsets.ModelViewSet):
    queryset = SendBatchStatus.objects.all().order_by("position", "token", "id")
    serializer_class = SendBatchStatusSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None


class SendBatchSettingsView(APIView):
    """
    Vista agregada de configuració SendBatch.

    GET  → estat actual + el que falta respecte als valors esperats
    POST → crea els registres/config que falten (tokens canònics)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(get_send_batch_settings_overview())

    def post(self, request):
        result = ensure_send_batch_defaults(user=request.user)
        return Response(result, status=status.HTTP_200_OK)
