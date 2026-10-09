from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from coredata.models import ConfigProject
from claimrequest.serializers import (
    ClaimRequestStepTemplateSerializer,
    ClaimRequestSerializer
)

from billing.models import InvoiceLineItem
from billing.serializers.invoice_line_item_serializer import (
    InvoiceLineItemSaveSerializer,
    InvoiceLineItemSerializer
)
from billing.filter.invoice_line_item_filter import InvoiceLineItemFilter
from billing.utils.invoice_service import update_invoice_totals
from billing.permissions import InvoicePermission
class InvoiceLineItemViewSet(viewsets.ModelViewSet):
    queryset = InvoiceLineItem.objects.filter(is_active=True).order_by('-product__order_priority', 'name')
    serializer_class = InvoiceLineItemSerializer
    permission_classes = [IsAuthenticated, InvoicePermission]
    filterset_class = InvoiceLineItemFilter
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields = ['token','name']
    ordering_fields = ['token','name']
    lookup_field = 'id'

    def get_serializer_class(self):
        if self.request.method in ['GET']:
            return InvoiceLineItemSerializer
        return InvoiceLineItemSaveSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = InvoiceLineItemSerializer(instance)
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = InvoiceLineItemSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_200_OK, content_type='application/json')
    
    def destroy(self, request, *args, **kwargs):
        invoice_type_token = ConfigProject.objects.get(token='invoice_type_invoice_token').value
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        update_invoice_totals(instance.invoice)
        instance.invoice.manually_modified = instance.invoice.type.token == invoice_type_token
        instance.invoice.save()
        return Response(status=status.HTTP_204_NO_CONTENT)