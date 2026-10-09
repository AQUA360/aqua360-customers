from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from ..models import Order
from order.utils.order_pdf import generate_order_pdf   # tu función ya creada


class OrderReportPDFDownloadViewSet(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Order.objects.all().order_by('-created_at')

    def get(self, request, id, *args, **kwargs):
        order = get_object_or_404(Order, id=id)
        context = {'request': request}

        file_url, document_id, _ = generate_order_pdf(
            order=order,
            request=request,
            context=context,
            save_pdf=True
        )

        return JsonResponse({
            "pdf_url": file_url,
            "document_id": document_id
        })
