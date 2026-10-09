from io import BytesIO

from django.http import HttpResponse, JsonResponse
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.views import APIView

from PyPDF2 import PdfMerger

from billing.models import Invoice
from claimrequest.models import ClaimRequest, ClaimRequestPayment
from claimrequest.permissions import ClaimRequestPermission
from claimrequest.tasks import generate_claim_document_pdf
from documentmanager.utils.sign_certificate_service import sign_pdf
from service.models import Exploitation
from service.serializers.company_serializer import CompanySerializer

class ClaimDocumentPDFDownloadViewSet(APIView):
    permission_classes = [IsAuthenticated, ClaimRequestPermission]
    queryset = ClaimRequest.objects.all().order_by('-created_at')
    def put(self, request, id, *args, **kwargs):
        print("in generating claim document pdf")
        claim_request = ClaimRequest.objects.get(id=id)
        claim_payments = ClaimRequestPayment.objects.filter(claim_request=claim_request)
        #get contract in each claim payment in contracts
        contracts = [cp.contract for cp in claim_payments]
        
        step_id = request.data.get("step_id", None)
        
        task_results = []
        print("before going into contract generation")
        for contract in contracts:
            task_result = generate_claim_document_pdf.delay(claim_request.id, contract.id, step_id)
            task_results.append(task_result)
        
        pdf_buffers = []
        for task_result in task_results:
            try:
                result = task_result.get(timeout=60)  
                if result["status"] == "success":
                    pdf_buffers.append(BytesIO(result["pdf_content"]))
                else:
                    
                    print(f"Task failed: {result['message']}")
                    
            except Exception as e:
                
                print(f"Error getting task result: {e}")
        
        merger = PdfMerger()
        for pdf_buffer in pdf_buffers:
            merger.append(pdf_buffer)

        merged_pdf_buffer = BytesIO()
        merger.write(merged_pdf_buffer)
        merger.close()
        
        exploitation = Exploitation.objects.filter(is_active=True).first()
        company = CompanySerializer(exploitation.company).data
        
        #SIGNATURE
        signed_pdf_buffer = sign_pdf(
            merged_pdf_buffer, 
            company, 
            claim_request.current_step.document_type.name if claim_request.current_step.document_type else '',
            claim_request.current_step.document_type.token if claim_request.current_step.document_type else ''
            )

        response = HttpResponse(
            signed_pdf_buffer.getvalue(), content_type="application/pdf"
        )
        response[
            "Content-Disposition"
        ] = f'attachment; filename="claim_documents_{id}.pdf"'

        return response
