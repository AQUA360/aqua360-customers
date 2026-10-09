from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from service.models import ConnectionRequest
from billing.serializers.invoice_serializer import InvoiceSerializer
from billing.utils.invoice_service import invoice_connection_generate

class InvoiceConnectionGenerateView(views.APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = ConnectionRequest.objects.all().order_by('-created_at')
    def put(self, request, connection_request_id):
        try:
            # Validar les dades rebudes
            
            if not connection_request_id:
                return Response({"error": "Contract ID is required."}, status=status.HTTP_400_BAD_REQUEST)
            
            title = request.data.get('title')
            payment_type = request.data.get('payment_type')
            payment_bank = request.data.get('payment_bank')
            # TODO: Cridar la funció de servei
            invoice = invoice_connection_generate(request.user, connection_request_id, title)
            # Serialitzar la resposta
            serializer = InvoiceSerializer(invoice)
            return Response(serializer.data, status=status.HTTP_200_OK)
            #return Response({"error": "Invoice not generated yet."}, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
