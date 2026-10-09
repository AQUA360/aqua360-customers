import datetime
from django.core.files.storage import default_storage
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from django.core.files.base import ContentFile
from billing.models import Billing, Invoice
from billing.utils.generate_factdeta_service import *
from billing.utils.aca_company_service import ACACompanyError
from service.models import Exploitation
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

class DetailedBillingDocumentGenerateView(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Billing.objects.all().order_by('-created_at')
    
    def put(self, request, *args, **kwargs):
        print("In Detailed Billing Document Generate View")
        # FACDETA
        is_alta = request.data.get('is_alta', False)
        exploitations = Exploitation.objects.filter(is_active=True)
        invoices = Invoice.objects.filter(
            is_active=True,
            payments__is_active=True,
            issue_date__gte=datetime.date(2026,8,17),
        )
        # Amb múltiples empreses cada fitxer ACA és d'una sola empresa (veure resolve_aca_company)
        company_id = request.data.get('company_id', None)
        if company_id:
            invoices = invoices.filter(company_id=company_id)
        try:
            files = generate_factdeta_document(exploitations, invoices, is_alta)
        except ACACompanyError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        file_urls = []
        for file_data in files:
            file = ContentFile(file_data["content"], name=file_data["file_name"])
            temp_rel_path = f"tmp/FACDETA/{file_data['file_name']}"
            saved_path = default_storage.save(temp_rel_path, file)
            file_url = request.build_absolute_uri(default_storage.url(saved_path))
            file_urls.append({
                "year": file_data["year"],
                "file_url": file_url,
                "file_name": file_data["file_name"],
            })
        
        if file_urls:
            return Response({"files": file_urls, "message": "Files generated successfully"}, status=status.HTTP_200_OK)
        
        return Response({"error": "No invoices found"}, status=status.HTTP_404_NOT_FOUND)
