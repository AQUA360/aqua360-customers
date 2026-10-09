from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat

from documentmanager.utils.main_utils import upload_document

from ..models import OrderReport, OrderReportDocument
from ..serializers.order_report_serializer import OrderReportDocumentSerializer
from ..filters.order_report_document_filter import OrderReportDocumentFilter
from order.permissions import OrderPermission
class OrderReportDocumentViewSet(viewsets.ModelViewSet):
    queryset = OrderReportDocument.objects.all().order_by('id')
    permission_classes = [IsAuthenticated, OrderPermission]
    filter_backends = (DjangoFilterBackend,)
    filterset_class = OrderReportDocumentFilter
    search_fields = ['type','file']
    ordering_fields = ['type','file']
    
    def get_serializer_class(self):
        return OrderReportDocumentSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        order_report = OrderReport.objects.get(id=request.data.get('id'))
        request.data.pop('id')
        file = request.data.pop('file')
        print(request.FILES)
        
        serializer.is_valid(raise_exception=True)
        
        service = settings.DOCUMENT_MANAGER_SERVICES.get("order")
        document = upload_document(file[0], order_report.order.token, 'ORDER', order_report.id, order_report.token, '', service, file[0].name)
        validated_data = serializer.validated_data
        validated_data['order_report'] = order_report
        validated_data['file'] = document 
        
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = OrderReportDocumentSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers, content_type='application/json')

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = OrderReportDocumentSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_200_OK, content_type='application/json')