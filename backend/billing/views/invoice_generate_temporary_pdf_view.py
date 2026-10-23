# contract/views/contract_request_finalize_view.py

from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from billing.models import Invoice
from billing.utils.invoice_pdf import generate
from service.models import Exploitation
from django.shortcuts import get_object_or_404
import logging

logger = logging.getLogger(__name__)

class InvoiceGenerateTemporaryPDFView(views.APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Invoice.objects.all().order_by('-created_at')
    def get(self, request, id):
        """Generate a temporary invoice PDF and return its absolute URL.

        Return HTTP 500 if generation or URL resolution fails, logging internal
        errors and returning a generic message.
        """
        try:
            if not id:
                return Response({"error": "Invoice id is required."}, status=status.HTTP_400_BAD_REQUEST)
            invoice = get_object_or_404(Invoice, id=id)
            print("got invoice")
            exploitation = invoice.exploitation if invoice.exploitation else Exploitation.objects.filter(is_active=True).first()
            context = {'request': request}
            print("going to generate pdf")
            generate(context, invoice, exploitation, True)
            
            new_invoice = get_object_or_404(Invoice, id=id)
            # El PDF amb marca d'aigua es desa a invoice_file_template; el definitiu,
            # només al gestor documental (invoice_file).
            if new_invoice.invoice_file_template and new_invoice.invoice_file_template.name:
                try:
                    file_url = request.build_absolute_uri(new_invoice.invoice_file_template.url)
                except ValueError:
                    logger.exception("No s'ha pogut obtenir l'URL del PDF")
                    return Response({"error": "No s'ha pogut obtenir l'URL del PDF."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            elif new_invoice.invoice_file_id:
                file_url = request.build_absolute_uri(f"/documentmanager/view-document/{new_invoice.invoice_file_id}/")
            else:
                return Response({"error": "No s'ha pogut generar el PDF. El fitxer no s'ha guardat correctament."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            return Response({"url": file_url}, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.exception("Error inesperat")
            return Response({"error": "Ha ocorregut un error inesperat."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
