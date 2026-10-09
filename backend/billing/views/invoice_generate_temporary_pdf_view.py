# contract/views/contract_request_finalize_view.py

from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from billing.models import Invoice
from billing.utils.invoice_pdf import generate
from service.models import Exploitation
from django.shortcuts import get_object_or_404

class InvoiceGenerateTemporaryPDFView(views.APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Invoice.objects.all().order_by('-created_at')
    def get(self, request, id):
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
            # Check if the file was successfully saved before accessing its URL
            if not new_invoice.invoice_file_template or not new_invoice.invoice_file_template.name:
                return Response({"error": "No s'ha pogut generar el PDF. El fitxer no s'ha guardat correctament."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Get the full URL including host
            print(new_invoice.invoice_file_template)
            try:
                file_url = request.build_absolute_uri(new_invoice.invoice_file_template.url)
            except ValueError as e:
                return Response({"error": f"No s'ha pogut obtenir l'URL del PDF: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            return Response({"url": file_url}, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
