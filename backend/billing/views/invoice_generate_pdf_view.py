from django.http import FileResponse, JsonResponse
from rest_framework.views import APIView
from io import BytesIO
from xhtml2pdf import pisa
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from billing.models import Invoice

class InvoiceGeneratePDFViewSet(APIView):
  permission_classes = [IsAuthenticated, DjangoModelPermissions]
  queryset = Invoice.objects.all().order_by('-created_at')
  def post(self, request, *args, **kwargs):

    html_content = request.data.get('html_template')
    if not html_content:
        return JsonResponse({"error": "No HTML content provided"}, status=400)

    pdf_buffer = BytesIO()

    pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)
    if pisa_status.err:
        return JsonResponse({"error": "PDF generation failed"}, status=500)

    # Save PDF to `contract_file` field in Invoice instance
    pdf_buffer.seek(0)

    # Create a response that serves the PDF file
    response = FileResponse(pdf_buffer, as_attachment=True, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="invoice_template.pdf"'
    return response