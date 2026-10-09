from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django.db import transaction

from billing.models import Billing, BillingStatus, Invoice, InvoiceLineItem, InvoiceLog, Payment
from coredata.models import ConfigProject


def _delete_pre_invoice(invoice):
    invoice_id = invoice.id
    InvoiceLog.objects.filter(invoice_id=invoice_id).delete()
    InvoiceLineItem.objects.filter(invoice_id=invoice_id).delete()
    Payment.objects.filter(invoice_id=invoice_id).delete()
    invoice.readings.clear()
    invoice.general_contracts.clear()
    if invoice.invoice_file_id:
        invoice.invoice_file.delete()
    Invoice.objects.filter(parent_invoice_id=invoice_id).update(parent_invoice=None)
    invoice.delete()


class ExcludeInvoiceView(views.APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Invoice.objects.all()

    def post(self, request, *args, **kwargs):
        try:
            invoice_ids = request.data.get('invoice_ids')
            invoice_id = request.data.get('invoice_id')

            if not invoice_ids and invoice_id:
                invoice_ids = [invoice_id]

            if not invoice_ids:
                return Response({"error": "Missing invoice_ids"}, status=status.HTTP_400_BAD_REQUEST)

            invoices = list(
                Invoice.objects.filter(id__in=invoice_ids).select_related('status', 'billing')
            )
            if not invoices:
                return Response({"error": "No valid invoices found"}, status=status.HTTP_404_NOT_FOUND)

            try:
                pending_invoice_token = ConfigProject.objects.get(token='invoice_status_pending_token').value
            except ConfigProject.DoesNotExist:
                pending_invoice_token = "1"

            # is_confirmed es True des de la creació de la pre-factura; no indica
            # que ja s'hagi confirmat. Només es bloqueja si l'estat ja no és pre-factura.
            not_preinvoice = [
                invoice for invoice in invoices
                if not invoice.is_excluded and (
                    not invoice.status_id or invoice.status.token != pending_invoice_token
                )
            ]
            if not_preinvoice:
                return Response(
                    {"error": "Only pending pre-invoices can be excluded."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            pending_status = BillingStatus.objects.filter(is_default=True).first()
            deleted = 0
            included = 0

            with transaction.atomic():
                for invoice in invoices:
                    if invoice.is_excluded:
                        readings = invoice.readings.all()
                        if readings.exists():
                            first_reading = readings.first()
                            excluded_billing = first_reading.billing
                            if excluded_billing and excluded_billing.is_excluded and excluded_billing.excluded_from:
                                readings.update(billing=excluded_billing.excluded_from)
                                if not excluded_billing.readings.exists():
                                    excluded_billing.delete()
                        invoice.is_excluded = False
                        invoice.save(update_fields=['is_excluded'])
                        included += 1
                        continue

                    billing = invoice.billing
                    readings = invoice.readings.all()
                    if billing and readings.exists():
                        exclude_billing, _created = Billing.objects.get_or_create(
                            excluded_from=billing,
                            is_excluded=True,
                            defaults={
                                'status': pending_status,
                                'name': f"EX-{billing.name}",
                                'token': f"EXI-{billing.token}",
                                'biller': billing.biller,
                                'is_active': True,
                            },
                        )
                        if billing.biller_id and not exclude_billing.biller_id:
                            exclude_billing.biller = billing.biller
                            exclude_billing.save(update_fields=['biller'])
                        if not exclude_billing.routes.exists():
                            exclude_billing.routes.set(billing.routes.all())
                        readings.update(billing=exclude_billing)

                    _delete_pre_invoice(invoice)
                    deleted += 1

            return Response({
                "message": f"{deleted} pre-invoices deleted and {included} invoices included",
                "deleted": deleted,
                "included": included,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"Unexpected error occurred: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
