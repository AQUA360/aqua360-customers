from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from billing.models import Invoice
from billing.utils.invoice_range_utils import filter_invoices_by_serie_final_range, split_serie_final
from coredata.models import ConfigProject

GENERAL_BILLING_SUMMARY_PREVIEW_CONFIG_TOKEN = 'general_billing_summary_preview_enabled'


def general_billing_summary_preview_enabled():
    try:
        value = ConfigProject.objects.get(token=GENERAL_BILLING_SUMMARY_PREVIEW_CONFIG_TOKEN).value
    except ConfigProject.DoesNotExist:
        return False
    return str(value).strip().lower() in ('true', '1', 'yes')


def _serialize_invoice(invoice):
    return {
        'id': invoice.id,
        'serie_final': invoice.serie_final,
        'issue_date': invoice.issue_date,
        'customer_final': invoice.customer_final,
        'total_final': invoice.total_final,
        'reviewed': invoice.reviewed,
        'is_excluded': invoice.is_excluded,
    }


class InvoiceReviewedRangePreviewView(views.APIView):
    """Previsualitzacio, abans de generar el "Resum de la facturacio general" o de
    marcar un rang com a revisat, de: les factures que es generaran, les que han
    quedat "perdudes" (sense revisar) entre l'ultima factura revisada d'aquesta serie
    i l'inici del rang actual, i les que ja estaven revisades dins el propi rang
    (excloses de "to_generate" perque no es tornin a incloure a l'informe). Nomes
    disponible quan el ConfigProject `general_billing_summary_preview_enabled`
    esta activat."""
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Invoice.objects.all()

    def post(self, request, *args, **kwargs):
        try:
            if not general_billing_summary_preview_enabled():
                return Response({"error": "La previsualitzacio no esta activada per a aquest projecte."}, status=status.HTTP_403_FORBIDDEN)

            serie_final_from = request.data.get('serie_final_from')
            serie_final_to = request.data.get('serie_final_to')
            prefix = request.data.get('prefix')
            # Filtre d'usuari: per defecte les factures ja revisades no es tornen a
            # incloure a "to_generate" (per no duplicar-les en una nova execució),
            # però l'usuari pot desmarcar-ho per veure-les/generar-les igualment.
            exclude_reviewed = request.data.get('exclude_reviewed', True)

            if serie_final_from is None or serie_final_to is None:
                return Response({"error": "serie_final_from and serie_final_to are required"}, status=status.HTTP_400_BAD_REQUEST)

            # Els numeros de factura poden portar prefix alfabetic (p.ex. "D1234567",
            # despeses d'impagats), per aixo no es validen amb int() ni s'hi passen
            # convertits: el filtre de rang necessita el prefix per acotar la serie.
            from_alpha, from_number = split_serie_final(serie_final_from)
            to_alpha, to_number = split_serie_final(serie_final_to)
            if from_number is None or to_number is None:
                return Response({"error": "serie_final_from and serie_final_to must be invoice numbers (e.g. 12345678 or D1234567)"}, status=status.HTTP_400_BAD_REQUEST)

            if int(from_number) > int(to_number):
                serie_final_from, serie_final_to = serie_final_to, serie_final_from
                from_alpha, from_number = to_alpha, to_number

            active_invoices = Invoice.objects.filter(is_active=True)

            range_invoices = filter_invoices_by_serie_final_range(
                active_invoices, serie_final_from, serie_final_to, prefix=prefix
            ).order_by('serie_final_num')

            # Les excloses (Invoice.is_excluded) sempre queden fora de "to_generate". Les ja
            # revisades (Invoice.reviewed) només se n'exclouen quan `exclude_reviewed` és cert
            # (per defecte); en tot cas es mostren sempre a "already_reviewed" per informar-ne.
            if exclude_reviewed:
                to_generate = [invoice for invoice in range_invoices if not invoice.is_excluded and not invoice.reviewed]
            else:
                to_generate = [invoice for invoice in range_invoices if not invoice.is_excluded]
            excluded = [invoice for invoice in range_invoices if invoice.is_excluded]
            already_reviewed = [invoice for invoice in range_invoices if not invoice.is_excluded and invoice.reviewed]

            # Extrem superior "una factura per sota del rang", mantenint el prefix
            # alfabetic perque la serie no es barregi amb les series numeriques.
            missing_to = f"{from_alpha}{int(from_number) - 1}"

            missing = list(
                filter_invoices_by_serie_final_range(active_invoices, None, missing_to, prefix=prefix)
                .filter(reviewed=False, is_excluded=False)
                .order_by('serie_final_num')
            )

            return Response({
                'to_generate': [_serialize_invoice(invoice) for invoice in to_generate],
                'to_generate_count': len(to_generate),
                'excluded': [_serialize_invoice(invoice) for invoice in excluded],
                'excluded_count': len(excluded),
                'already_reviewed': [_serialize_invoice(invoice) for invoice in already_reviewed],
                'already_reviewed_count': len(already_reviewed),
                'missing': [_serialize_invoice(invoice) for invoice in missing],
                'missing_count': len(missing),
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
