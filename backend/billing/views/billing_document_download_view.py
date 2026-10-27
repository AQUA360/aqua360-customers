import logging

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import serializers, status, views
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from billing.models import Billing, BillingDocumentDownload
from billing.utils.billing_document_download import (
    DownloadOptionsError,
    ordered_billing_invoices,
    ordered_process_files,
    parse_download_request,
)
from communication.models import CommunicationProcess
from documentmanager.utils.export_jobs import enqueue_export, export_job_response

logger = logging.getLogger(__name__)


class BillingDocumentDownloadPermission(BasePermission):
    """Facturació o el procés de comunicació, que és l'altre origen del panell."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return (
            user.has_perm('billing.view_billing')
            or user.has_perm('communication.view_communicationprocess')
        )


class BillingDocumentDownloadSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.SerializerMethodField()
    document_id = serializers.IntegerField(read_only=True, allow_null=True)
    document_name = serializers.SerializerMethodField()
    source = serializers.SerializerMethodField()
    billing_ids = serializers.SerializerMethodField()
    billing_tokens = serializers.SerializerMethodField()
    communication_process_token = serializers.SerializerMethodField()

    class Meta:
        model = BillingDocumentDownload
        fields = [
            'id', 'source', 'billing_ids', 'billing_tokens', 'communication_process',
            'communication_process_token', 'payment_type_tokens', 'delivery', 'ordering',
            'descending', 'invoice_count', 'status', 'error_message', 'document_id',
            'document_name', 'created_at', 'completed_at', 'requested_by_name',
        ]

    def get_requested_by_name(self, obj):
        user = obj.requested_by
        if user is None:
            return None
        full_name = user.get_full_name()
        return full_name or user.username

    def get_document_name(self, obj):
        if obj.document_id is None:
            return None
        return obj.document.document_name

    def get_source(self, obj):
        return 'process' if obj.communication_process_id else 'billings'

    def _billings(self, obj):
        billings = list(obj.billings.all())
        if billings:
            return billings
        if obj.billing_id and obj.billing is not None:
            return [obj.billing]
        return []

    def get_billing_ids(self, obj):
        return [billing.id for billing in self._billings(obj)]

    def get_billing_tokens(self, obj):
        return [billing.token for billing in self._billings(obj)]

    def get_communication_process_token(self, obj):
        process = obj.communication_process
        if process is None:
            return None
        return process.token


def reconcile_download(record):
    """Si la tasca ja ha acabat i la fila no s'ha assabentat, l'actualitza."""
    if record.status not in BillingDocumentDownload.ACTIVE_STATUSES or not record.task_id:
        return record
    try:
        from celery.result import AsyncResult
        state = AsyncResult(record.task_id).state
    except Exception:
        logger.exception("No s'ha pogut consultar l'estat de la descàrrega %s", record.id)
        return record

    if state == 'STARTED' and record.status == BillingDocumentDownload.STATUS_PENDING:
        record.status = BillingDocumentDownload.STATUS_RUNNING
        record.save(update_fields=['status'])
    elif state in ('FAILURE', 'REVOKED'):
        record.status = BillingDocumentDownload.STATUS_FAILED
        record.error_message = record.error_message or state
        record.completed_at = timezone.now()
        record.save(update_fields=['status', 'error_message', 'completed_at'])
    return record


def _options_error(exc):
    messages = {
        'delivery': _("El filtre de carta o correu només es pot fer des d'un procés de comunicació."),
        'source': _("Selecciona facturacions o un procés de comunicació."),
        'billing_ids': _("Les facturacions indicades no són vàlides."),
    }
    return Response(
        {"error": exc.field, "message": messages.get(exc.field, _("Els filtres de la descàrrega no són vàlids."))},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _history():
    records = list(
        BillingDocumentDownload.objects.select_related(
            'requested_by', 'document', 'billing', 'communication_process',
        ).prefetch_related('billings')[:100]
    )
    for record in records:
        reconcile_download(record)
    return records


class BillingDocumentDownloadPreviewView(views.APIView):
    permission_classes = [IsAuthenticated, BillingDocumentDownloadPermission]

    def get(self, request):
        try:
            options = parse_download_request(request.query_params)
            count = _selection_count(options)
        except DownloadOptionsError as exc:
            return _options_error(exc)
        return Response({"count": count})


class BillingDocumentDownloadView(views.APIView):
    permission_classes = [IsAuthenticated, BillingDocumentDownloadPermission]

    def get(self, request):
        return Response(BillingDocumentDownloadSerializer(_history(), many=True).data)

    def post(self, request):
        try:
            options = parse_download_request(request.data)
        except DownloadOptionsError as exc:
            return _options_error(exc)

        process = None
        billings = []
        try:
            if options['communication_process_id']:
                process = get_object_or_404(CommunicationProcess, id=options['communication_process_id'])
                count = len(ordered_process_files(
                    process.id,
                    payment_type_tokens=options['payment_type_tokens'],
                    delivery=options['delivery'],
                    ordering=options['ordering'],
                    descending=options['descending'],
                ))
                if not count:
                    return Response(
                        {"error": "no_documents", "message": _("No hi ha documents amb aquests filtres.")},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                billings = list(Billing.objects.filter(id__in=options['billing_ids']))
                if len(billings) != len(options['billing_ids']):
                    raise DownloadOptionsError('billing_ids')
                count = ordered_billing_invoices(
                    options['billing_ids'],
                    payment_type_tokens=options['payment_type_tokens'],
                    ordering=options['ordering'],
                    descending=options['descending'],
                ).count()
                if not count:
                    return Response(
                        {"error": "no_invoices", "message": _("No hi ha factures amb aquests filtres.")},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
        except DownloadOptionsError as exc:
            return _options_error(exc)

        from billing.tasks import generate_billing_document_download

        with transaction.atomic():
            record = BillingDocumentDownload.objects.create(
                billing=billings[0] if len(billings) == 1 else None,
                communication_process=process,
                requested_by=request.user if request.user.is_authenticated else None,
                payment_type_tokens=options['payment_type_tokens'],
                delivery=options['delivery'],
                ordering=options['ordering'],
                descending=options['descending'],
                invoice_count=count,
            )
            if billings:
                record.billings.set(billings)
            name = _download_name(billings, process)
            job = enqueue_export(
                request,
                generate_billing_document_download,
                kind="billing_documents",
                name=name,
                args=[record.id],
                params={
                    "billing_ids": [billing.id for billing in billings],
                    "communication_process_id": process.id if process else None,
                    "download_id": record.id,
                    "delivery": options['delivery'],
                    "ordering": options['ordering'],
                    "descending": options['descending'],
                    "payment_type_tokens": options['payment_type_tokens'],
                    "invoice_count": count,
                },
            )
            record.task_id = job.task_id
            record.save(update_fields=['task_id'])

        payload = export_job_response(job)
        payload['download'] = BillingDocumentDownloadSerializer(record).data
        return Response(payload, status=status.HTTP_202_ACCEPTED)


def _selection_count(options):
    if options['communication_process_id']:
        get_object_or_404(CommunicationProcess, id=options['communication_process_id'])
        return len(ordered_process_files(
            options['communication_process_id'],
            payment_type_tokens=options['payment_type_tokens'],
            delivery=options['delivery'],
            ordering=options['ordering'],
            descending=options['descending'],
        ))
    found = Billing.objects.filter(id__in=options['billing_ids']).count()
    if found != len(options['billing_ids']):
        raise DownloadOptionsError('billing_ids')
    return ordered_billing_invoices(
        options['billing_ids'],
        payment_type_tokens=options['payment_type_tokens'],
        ordering=options['ordering'],
        descending=options['descending'],
    ).count()


def _download_name(billings, process):
    if process is not None:
        name = str(_("Procés"))
        if process.token:
            name = f"{name} {process.token}"
        return name
    name = str(_("Factures"))
    tokens = [billing.token for billing in billings if billing.token]
    if tokens:
        name = f"{name} {', '.join(tokens)}"
    return name[:255]
