# contract/views/contract_request_finalize_view.py

from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from contract.models import Contract, ContractRequest
from coredata.models import ConfigProject

from billing.models import Invoice
from billing.serializers.invoice_serializer import InvoiceSerializer
from billing.utils.invoice_service import invoice_contract_generate, invoice_generate_return_bail

class InvoiceContractGenerateView(views.APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = ContractRequest.objects.all().order_by('-created_at')
    def put(self, request, contract_request_id):
        try:
            # Validar les dades rebudes
            
            if not contract_request_id:
                return Response({"error": "Contract ID is required."}, status=status.HTTP_400_BAD_REQUEST)
            
            title = request.data.get('title')
            payment_type = request.data.get('payment_type')
            payment_bank = request.data.get('payment_bank')
            company_bank = request.data.get('company_iban') or request.data.get('company_bank')
            
            is_return = request.data.get('is_return')
            print("PAYMENT ID")
            print(payment_bank)
            invoice_type_token = request.data.get('invoice_type_token')
            company_id = request.data.get('company_id')
            category_id = request.data.get('category_id')
            # Cridar la funció de servei
            if is_return:
                invoice = invoice_generate_return_bail(request.user, contract_request_id, title, payment_type, payment_bank, is_return, None, request.data['electronicInvoiceData'], False, company_bank)
            else:
                invoice = invoice_contract_generate(request.user, contract_request_id, title, payment_type, payment_bank, is_return, None, request.data['electronicInvoiceData'], False, company_bank, company_id=company_id, category_id=category_id)
            # Serialitzar la resposta
            serializer = InvoiceSerializer(invoice)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
