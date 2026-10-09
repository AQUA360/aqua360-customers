from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from customers.queue_utils import QueueTaskRevokeError
from documentmanager.models import ExportJob
from documentmanager.serializers import ExportJobSerializer
from documentmanager.utils.export_jobs import cancel_job, reconcile_job


class ExportJobPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ExportJobViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin,
                       viewsets.GenericViewSet):
    """
    Cua de descàrregues de l'usuari connectat (`/documentmanager/export-job/`).

    - GET  /                 → les seves descàrregues (actives primer, després les més recents).
                               `?active=true` només les pendents/en curs.
    - GET  /<id>/            → una descàrrega.
    - DELETE /<id>/          → la treu del panell (no esborra el document).
    - POST /<id>/cancel/     → atura una descàrrega pendent o en curs.
    - POST /clear-finished/  → treu del panell totes les acabades.

    Cada usuari només veu les seves: no hi ha cap permís per veure les dels altres.
    """
    serializer_class = ExportJobSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ExportJobPagination

    def get_queryset(self):
        qs = ExportJob.objects.filter(requested_by=self.request.user, dismissed_at__isnull=True)
        if self.request.query_params.get("active") in ("true", "1"):
            qs = qs.filter(status__in=ExportJob.ACTIVE_STATUSES)
        return qs.order_by("-created_at")

    def list(self, request, *args, **kwargs):
        # Les actives poden haver acabat sense que el signal hagi arribat: es reconcilien abans de llistar.
        for job in self.get_queryset().filter(status__in=ExportJob.ACTIVE_STATUSES):
            reconcile_job(job)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        job = reconcile_job(self.get_object())
        return Response(self.get_serializer(job).data)

    def perform_destroy(self, instance):
        instance.dismissed_at = timezone.now()
        instance.save(update_fields=["dismissed_at"])

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        job = self.get_object()
        if not job.is_active:
            return Response({"detail": "Export is not running"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            cancel_job(job)
        except QueueTaskRevokeError as e:
            return Response({"detail": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(self.get_serializer(job).data)

    @action(detail=False, methods=["post"], url_path="clear-finished")
    def clear_finished(self, request):
        updated = self.get_queryset().exclude(status__in=ExportJob.ACTIVE_STATUSES).update(dismissed_at=timezone.now())
        return Response({"dismissed": updated})
