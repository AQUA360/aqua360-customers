from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from billing.models import Invoice
from billing.utils.invoice_range_utils import filter_invoices_by_serie_final_range, split_serie_final


class InvoiceMarkReviewedRangeView(views.APIView):
    """Marca (o desmarca) com a revisades totes les factures actives amb numero de
    factura (serie_final) dins el rang [serie_final_from, serie_final_to], seguint
    el mateix criteri de rang que feia servir l'antic sistema Kais."""
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Invoice.objects.all()

    def post(self, request, *args, **kwargs):
        try:
            serie_final_from = request.data.get('serie_final_from')
            serie_final_to = request.data.get('serie_final_to')
            prefix = request.data.get('prefix')
            reviewed = request.data.get('reviewed', True)

            if serie_final_from is None or serie_final_to is None:
                return Response({"error": "serie_final_from and serie_final_to are required"}, status=status.HTTP_400_BAD_REQUEST)

            # Els numeros de factura poden portar prefix alfabetic (p.ex. "D1234567",
            # despeses d'impagats), per aixo no es validen amb int() ni s'hi passen
            # convertits: el filtre de rang necessita el prefix per acotar la serie.
            _, from_number = split_serie_final(serie_final_from)
            _, to_number = split_serie_final(serie_final_to)
            if from_number is None or to_number is None:
                return Response({"error": "serie_final_from and serie_final_to must be invoice numbers (e.g. 12345678 or D1234567)"}, status=status.HTTP_400_BAD_REQUEST)

            if int(from_number) > int(to_number):
                serie_final_from, serie_final_to = serie_final_to, serie_final_from

            invoices = filter_invoices_by_serie_final_range(
                Invoice.objects.filter(is_active=True, is_excluded=False), serie_final_from, serie_final_to, prefix=prefix
            )

            updated_count = invoices.update(reviewed=bool(reviewed))

            return Response({
                "message": f"{updated_count} invoices marked as {'reviewed' if reviewed else 'not reviewed'}",
                "count": updated_count,
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
