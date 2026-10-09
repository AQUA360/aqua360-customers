from django.conf import settings
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.http import FileResponse, JsonResponse
from django.core.files.base import ContentFile
from rest_framework.views import APIView, Response
from io import BytesIO
from xhtml2pdf import pisa
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from coredata.serializers import AddressSerializer, PersonCardSerializer
from coredata.utils.template_utils import build_template_candidates
from documentmanager.utils.sign_certificate_service import sign_pdf
from service.serializers.company_serializer import CompanySerializer
from ..models import ContractRequest

class ProcessACADocumentViewSet(APIView):
  permission_classes = [IsAuthenticated, DjangoModelPermissions]
  queryset = ContractRequest.objects.all().order_by('-created_at')
  def get(self, request, id, *args, **kwargs):
    contract_request = get_object_or_404(ContractRequest, id=id)

    company = None
    city = None

    if (contract_request.supply_point is not None and
        contract_request.supply_point.connection is not None and
        contract_request.supply_point.connection.exploitation is not None and
        contract_request.supply_point.connection.exploitation.company is not None):
      context = {'request': request}
      company = CompanySerializer(contract_request.supply_point.connection.exploitation.company,context=context).data
    if (contract_request.supply_point is not None and
        contract_request.supply_point.address is not None and
        contract_request.supply_point.address.city is not None):
      city = contract_request.supply_point.address.city.name

    holder = PersonCardSerializer(contract_request.holder, context=context).data if contract_request.holder else None
    
    supply_address = AddressSerializer(contract_request.supply_point.address).data if contract_request.supply_point.address else None

    diameter = 15
    clauses = []

    if (contract_request.clauses.exists()):
      for clause in contract_request.clauses.all():
        clauses.append(clause)

    # Render HTML content
    contract_lang = contract_request.language or settings.LANGUAGE_CODE
    contract_template = build_template_candidates("contract_template.html", lang=contract_lang)
    html_content = render_to_string(contract_template, {'clauses':clauses,'diameter': diameter, 'request': contract_request, 'company': company, 'city': city, 'holder': holder, 'supply_address': supply_address})
    pdf_buffer = BytesIO()

    # Generate PDF from HTML
    pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)
    if pisa_status.err:
        return JsonResponse({"error": "PDF generation failed"}, status=500)
    
    #SIGNATURE
    signed_pdf_buffer = sign_pdf(pdf_buffer, company, 'CONTRACTE', 'CONTRACTE')
    
    # Save PDF to `contract_file` field in ContractRequest instance
    pdf_filename = f"contract_request_{id}.pdf"
    contract_request.contract_file.save(pdf_filename, ContentFile(signed_pdf_buffer.getvalue()))

    # Return the URL to the saved PDF file
    file_url = request.build_absolute_uri(contract_request.contract_file.url)
    return JsonResponse({"pdf_url": file_url})
