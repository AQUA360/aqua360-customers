import datetime

from django.core.files.storage import default_storage
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from django.core.files.base import ContentFile
from billing.models import Billing
from billing.utils.sgt_txt_service import generate_sgt_txt_content
from service.models import SupplyPoint
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions


class GenerateSgtTxsDocumentView(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Billing.objects.all().order_by('-created_at')

    def put(self, request, *args, **kwargs):
        print("In Generate Sgt Txs Document View")

        current_year = datetime.datetime.now().year
        file_urls = []

        content_file, file_name = generate_sgt_txt_content(request, [])

        file = ContentFile(content_file.getvalue(), name=file_name)
        temp_rel_path = f"tmp/SGTTX/{file_name}"
        saved_path = default_storage.save(temp_rel_path, file)
        file_url = request.build_absolute_uri(default_storage.url(saved_path))
        file_urls.append({"year": current_year, "file_url": file_url, "file_name": file_name})

        if file_urls:
            return Response({"files": file_urls, "message": "Files generated successfully"}, status=status.HTTP_200_OK)

        return Response({"error": "No invoices found"}, status=status.HTTP_404_NOT_FOUND)


def get_total_homes(invoice, contract):
    meter = contract.supply_point_default.meter
    supply_points_contracts = SupplyPoint.objects.filter(meter=meter, contract__isnull=False).distinct()
    return supply_points_contracts.count()
