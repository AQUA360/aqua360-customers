import logging
from django.contrib.auth.models import Group
from django.db.models import Count, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from auth.permissions import PermissionManager
from coredata.models import ConfigProject
from integrations.models import SendBatch
from integrations.serializers.send_batch_serializer import (
    SendBatchDetailSerializer,
    SendBatchListSerializer,
)
from integrations.utils.send_batch_providers import (
    SendBatchProviderError,
    get_send_batch_service,
)

logger = logging.getLogger(__name__)


def _ok_aqua_ids_from_resends(batch: SendBatch) -> set:
    """aqua_id que en algun reenviament relacionat ja no estan en error."""
    ok_ids = set()
    for child in batch.resend_batches.all().only("id", "final_response"):
        results = (child.final_response or {}).get("results") or []
        for row in results:
            if not isinstance(row, dict):
                continue
            if row.get("status") in ("ok", "duplicate_ignored") and row.get("aqua_id"):
                ok_ids.add(str(row["aqua_id"]))
    return ok_ids


def _error_rows(batch: SendBatch) -> list:
    results = (batch.final_response or {}).get("results") or []
    return [r for r in results if isinstance(r, dict) and r.get("status") == "error"]


def _pending_status_token() -> str:
    try:
        return ConfigProject.objects.get(token="send_batch_status_pending_token").value
    except ConfigProject.DoesNotExist:
        return "0"


def _processing_status_token() -> str:
    try:
        return ConfigProject.objects.get(token="send_batch_status_processing_token").value
    except ConfigProject.DoesNotExist:
        return "1"


def _has_send_error(batch: SendBatch) -> bool:
    if batch.instant_status_code and batch.instant_status_code >= 400:
        return True
    payload = batch.instant_response
    if isinstance(payload, dict) and payload.get("detail"):
        if not batch.sent_at or batch.instant_status_code in (None, 0):
            return True
        if batch.instant_status_code and batch.instant_status_code >= 400:
            return True
    return False


def _sent_without_immediate_error(batch: SendBatch) -> bool:
    if _has_send_error(batch):
        return False
    if not batch.sent_at:
        return False
    if batch.instant_status_code and batch.instant_status_code >= 400:
        return False
    return True


class SendBatchViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = [
        "token",
        "billing__token",
        "batch_type__token",
        "batch_type__name",
        "batch_type__provider__token",
        "batch_type__provider__name",
    ]
    ordering_fields = [
        "token",
        "batch_type__provider__token",
        "batch_type__token",
        "batch_type__name",
        "billing__token",
        "sent_at",
        "created_at",
        "finished_at",
        "status__token",
        "instant_status_code",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            SendBatch.objects.select_related(
                "batch_type",
                "batch_type__provider",
                "billing",
                "related_batch",
                "status",
            )
            .annotate(
                invoices_count_ann=Count("invoices", distinct=True),
                payments_count_ann=Count("payments", distinct=True),
                commitment_deposits_count_ann=Count(
                    "commitment_deposits", distinct=True
                ),
                observations_count_ann=Count(
                    "observations",
                    filter=Q(observations__is_active=True),
                    distinct=True,
                ),
            )
            .all()
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return SendBatchDetailSerializer
        return SendBatchListSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    @action(detail=False, methods=["get"], url_path="permissions")
    def permissions(self, request):
        pk = request.query_params.get("id")
        if pk:
            user_permissions = PermissionManager.get_model_permissions(
                request.user, "auth", "group"
            )
            if (
                not user_permissions["can_view"]
                or not user_permissions["can_change"]
                or not request.user.is_superuser
            ):
                return Response(None, status=status.HTTP_403_FORBIDDEN)
            group = Group.objects.filter(id=pk).first()
            if not group:
                return Response(None, status=status.HTTP_404_NOT_FOUND)
            group_permissions = PermissionManager.get_model_group_permissions(
                group, "invoice"
            )
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(
            request.user, "invoice", "billing"
        )
        return Response(permissions, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="items")
    def get_items(self, request, pk=None):
        batch = SendBatch.objects.get(id=pk)
        search = (request.query_params.get("search") or "").strip()
        page = int(request.query_params.get("page") or 1)
        page_size = int(request.query_params.get("page_size") or 50)
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)

        type_token = batch.batch_type.token if batch.batch_type else ""
        if type_token == "payments":
            qs = (
                batch.payments.select_related(
                    "payment__invoice__status",
                    "current_status",
                )
                .all()
                .order_by("-id")
            )
            if search:
                qs = qs.filter(
                    Q(token__icontains=search)
                    | Q(payment__invoice__serie_final__icontains=search)
                    | Q(payment__invoice__token__icontains=search)
                )
            object_kind = "payment"
        elif type_token in ("commitment_create", "commitment_cancel"):
            qs = (
                batch.commitment_deposits.select_related("status")
                .all()
                .order_by("-id")
            )
            if search:
                qs = qs.filter(
                    Q(token__icontains=search)
                    | Q(customer_final__icontains=search)
                    | Q(customer_token_final__icontains=search)
                )
            object_kind = "commitment_deposit"
        else:
            qs = batch.invoices.select_related("status").all().order_by("-id")
            if search:
                qs = qs.filter(
                    Q(token__icontains=search)
                    | Q(serie_final__icontains=search)
                    | Q(customer_final__icontains=search)
                    | Q(customer_token_final__icontains=search)
                )
            object_kind = "invoice"

        total = qs.count()
        start = (page - 1) * page_size
        end = start + page_size
        rows = []
        for obj in qs[start:end]:
            if object_kind == "invoice":
                rows.append(
                    {
                        "id": obj.id,
                        "kind": object_kind,
                        "token": obj.token,
                        "serie_final": obj.serie_final,
                        "issue_date": obj.issue_date,
                        "paid_at": getattr(obj, "paid_at", None),
                        "status_name": obj.status.name if obj.status else None,
                        "status_color": obj.status.color if obj.status else None,
                        "customer_final": obj.customer_final,
                        "customer_token_final": obj.customer_token_final,
                        "title_final": obj.title_final,
                        "left_to_pay": obj.left_to_pay,
                        "total_final": obj.total_final,
                        "label": obj.serie_final or obj.token,
                        "extra": obj.customer_final,
                    }
                )
            elif object_kind == "payment":
                payment = obj.payment
                invoice = getattr(payment, "invoice", None) if payment else None
                rows.append(
                    {
                        "id": obj.id,
                        "kind": object_kind,
                        "token": obj.token,
                        "payment_id": payment.id if payment else None,
                        "amount": getattr(payment, "amount", None),
                        "is_positive": obj.is_positive,
                        "movement_date": obj.movement_date,
                        "status_name": (
                            obj.current_status.name if obj.current_status else None
                        ),
                        "status_color": (
                            obj.current_status.color if obj.current_status else None
                        ),
                        "invoice_id": invoice.id if invoice else None,
                        "invoice_serie_final": getattr(invoice, "serie_final", None),
                        "label": obj.token,
                        "extra": getattr(invoice, "serie_final", None),
                    }
                )
            else:
                rows.append(
                    {
                        "id": obj.id,
                        "kind": object_kind,
                        "token": obj.token,
                        "customer_final": obj.customer_final,
                        "customer_token_final": obj.customer_token_final,
                        "total": obj.total,
                        "remaining": obj.remaining,
                        "status_name": obj.status.name if obj.status else None,
                        "status_color": obj.status.color if obj.status else None,
                        "label": obj.token,
                        "extra": obj.customer_final,
                    }
                )

        return Response(
            {
                "count": total,
                "page": page,
                "page_size": page_size,
                "object_kind": object_kind,
                "results": rows,
            }
        )

    @action(detail=True, methods=["get"], url_path="errors")
    def errors(self, request, pk=None):
        batch = self.get_object()
        blocked = _ok_aqua_ids_from_resends(batch)
        type_token = batch.batch_type.token if batch.batch_type else "invoices"
        if type_token == "payments":
            object_kind = "payment"
        elif type_token in ("commitment_create", "commitment_cancel"):
            object_kind = "commitment_deposit"
        else:
            object_kind = "invoice"

        rows = []
        for row in _error_rows(batch):
            aqua_id = str(row.get("aqua_id") or "")
            object_id = None
            payment_id = None
            invoice_id = None
            label = aqua_id
            if object_kind == "payment":
                mov = (
                    batch.payments.select_related("payment__invoice")
                    .filter(token=aqua_id)
                    .first()
                )
                object_id = mov.id if mov else None
                payment = mov.payment if mov else None
                payment_id = payment.id if payment else None
                invoice = getattr(payment, "invoice", None) if payment else None
                invoice_id = invoice.id if invoice else None
                if invoice and invoice.serie_final:
                    label = invoice.serie_final
                elif mov:
                    label = mov.token or aqua_id
            elif object_kind == "commitment_deposit":
                dep = batch.commitment_deposits.filter(token=aqua_id).first()
                object_id = dep.id if dep else None
                if dep:
                    label = dep.token or aqua_id
            else:
                inv = batch.invoices.filter(token=aqua_id).first()
                object_id = inv.id if inv else None
                invoice_id = object_id
                if inv:
                    label = inv.serie_final or inv.token or aqua_id
            rows.append(
                {
                    "aqua_id": aqua_id,
                    "object_kind": object_kind,
                    "object_id": object_id,
                    "payment_id": payment_id,
                    "invoice_id": invoice_id,
                    "label": label,
                    "message": row.get("message"),
                    "odoo_id": row.get("odoo_id"),
                    "blocked": aqua_id in blocked,
                    "blocked_reason": (
                        "already_ok_in_related_batch" if aqua_id in blocked else None
                    ),
                }
            )
        return Response(
            {"count": len(rows), "object_kind": object_kind, "results": rows}
        )

    @action(detail=True, methods=["post"], url_path="retry-send")
    def retry_send(self, request, pk=None):
        batch = self.get_object()
        pending_token = _pending_status_token()
        if not batch.status or batch.status.token != pending_token:
            return Response(
                {"detail": f"Només es pot reenviar un lot en estat '{pending_token}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Permetre reenviar si hi ha error d'enviament o el lot encara no s'ha enviat.
        if _sent_without_immediate_error(batch):
            return Response(
                {
                    "detail": (
                        "El lot ja s'ha enviat sense error immediat; "
                        "useu la consulta d'estat."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            svc = get_send_batch_service(batch)
        except SendBatchProviderError as exc:
            logger.exception("Failed to resolve send batch service for batch id=%s", batch.id)
            return Response(
                {"detail": "No s'ha pogut preparar el reenviament del lot."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            svc.retry_send_batch(batch)
        except (svc.api_error, svc.mapping_error) as exc:
            logger.exception("Failed to retry send batch id=%s", batch.id)
            return Response(
                {"detail": "No s'ha pogut reenviar el lot."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        batch.refresh_from_db()
        serializer = SendBatchDetailSerializer(batch, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="check-status")
    def check_status(self, request, pk=None):
        batch = self.get_object()
        processing_token = _processing_status_token()
        if not batch.status or batch.status.token != processing_token:
            return Response(
                {
                    "detail": (
                        f"Només es pot consultar l'estat d'un lot "
                        f"en estat '{processing_token}' (processing)."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not _sent_without_immediate_error(batch):
            return Response(
                {
                    "detail": (
                        "Cal que el lot s'hagi enviat sense error immediat "
                        "per consultar-ne l'estat."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            svc = get_send_batch_service(batch)
        except SendBatchProviderError as exc:
            logger.exception("Failed to resolve send batch service for status check, batch id=%s", batch.id)
            return Response(
                {"detail": "No s'ha pogut preparar la consulta d'estat del lot."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = svc.check_batch_status(batch)
        except svc.api_error as exc:
            logger.exception("Failed to check status for batch id=%s", batch.id)
            return Response(
                {"detail": "No s'ha pogut consultar l'estat del lot."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        batch.refresh_from_db()
        serializer = SendBatchDetailSerializer(batch, context={"request": request})
        return Response(
            {
                "status": result.get("status"),
                "message": result.get("message"),
                "summary": result.get("summary"),
                "batch": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="preview-payload")
    def preview_payload(self, request, pk=None):
        """
        Reconstrueix el JSON d'enviament {batch_id, items} per als aqua_id
        seleccionats (normalment objectes en error).
        """
        batch = self.get_object()
        aqua_ids = request.data.get("aqua_ids") or []
        if not isinstance(aqua_ids, list) or not aqua_ids:
            return Response(
                {"detail": "aqua_ids és obligatori (llista no buida)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        aqua_ids = [str(a) for a in aqua_ids]
        error_aqua = {str(r.get("aqua_id")) for r in _error_rows(batch) if r.get("aqua_id")}
        unknown = [a for a in aqua_ids if a not in error_aqua]
        if unknown:
            return Response(
                {"detail": f"aqua_id no estan en error en aquest lot: {unknown}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            svc = get_send_batch_service(batch)
        except SendBatchProviderError:
            return Response(
                {"detail": "No s'ha pogut inicialitzar el servei d'enviament."},
                status=status.HTTP_400_BAD_REQUEST,
            )
            logger.exception("Failed to build send payload preview for batch id=%s", batch.id)
            return Response(
                {"detail": "No s'ha pogut generar la previsualització del payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )
            payload = svc.build_send_payload_preview(batch, aqua_ids)
        except svc.api_error as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="resend-errors")
    def resend_errors(self, request, pk=None):
        batch = self.get_object()
        aqua_ids = request.data.get("aqua_ids") or []
        if not isinstance(aqua_ids, list) or not aqua_ids:
            return Response(
                {"detail": "aqua_ids és obligatori (llista no buida)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        aqua_ids = [str(a) for a in aqua_ids]
        error_aqua = {str(r.get("aqua_id")) for r in _error_rows(batch)}
        unknown = [a for a in aqua_ids if a not in error_aqua]
        if unknown:
            return Response(
                {"detail": f"aqua_id no estan en error en aquest lot: {unknown}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        blocked = _ok_aqua_ids_from_resends(batch)
        blocked_selected = [a for a in aqua_ids if a in blocked]
        if blocked_selected:
            return Response(
                {
                    "detail": (
                        "Aquests objectes ja no estan en error en un reenviament "
                        f"relacionat: {blocked_selected}"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
            logger.exception(
                "Failed to resolve send batch service for batch_id=%s",
                batch.id,
                exc_info=exc,
            )
            return Response(
                {"detail": "No s'ha pogut preparar el reenviament."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            svc = get_send_batch_service(batch)
        except SendBatchProviderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        type_token = batch.batch_type.token if batch.batch_type else "invoices"
        send = request.data.get("send", True)
        try:
            if type_token == "payments":
                ids = list(
                    batch.payments.filter(token__in=aqua_ids).values_list("id", flat=True)
                )
                if len(ids) != len(aqua_ids):
                    return Response(
                        {"detail": "No s'han trobat tots els moviments a reenviar."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                created = svc.push_payment_movement_batch(
                    ids,
                    billing=batch.billing,
                    related_batch=batch,
                    send=bool(send),
                )
            elif type_token in ("commitment_create", "commitment_cancel"):
                ids = list(
                    batch.commitment_deposits.filter(token__in=aqua_ids).values_list(
                        "id", flat=True
                    )
                )
                if len(ids) != len(aqua_ids):
                    return Response(
                        {"detail": "No s'han trobat tots els compromisos a reenviar."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                created = svc.push_commitment_deposit_batch(
                    ids,
                    action=(
                        "cancel" if type_token == "commitment_cancel" else "create"
                    ),
                    billing=batch.billing,
                    related_batch=batch,
                    send=bool(send),
                )
            else:
                ids = list(
                    batch.invoices.filter(token__in=aqua_ids).values_list("id", flat=True)
                )
                if len(ids) != len(aqua_ids):
                    return Response(
                        {"detail": "No s'han trobat totes les factures a reenviar."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                created = svc.push_invoice_batch(
                    ids,
                    billing=batch.billing,
                    related_batch=batch,
                    send=bool(send),
                )
        except (svc.api_error, svc.mapping_error) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = SendBatchDetailSerializer(
            created[0] if created else None, context={"request": request}
        )
        return Response(
            {
                "created": serializer.data if created else None,
                "batches": [
                    SendBatchDetailSerializer(b, context={"request": request}).data
                    for b in created
                ],
            },
            status=status.HTTP_201_CREATED,
        )

    def get_permissions(self):
        if self.action == "permissions":
            return [IsAuthenticated()]
        return super().get_permissions()
