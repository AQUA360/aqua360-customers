
import json
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from billing.models import Invoice, InvoiceLineItem
from billing.serializers.invoice_line_item_serializer import InvoiceLineItemSerializer
from billing.serializers.invoice_serializer import InvoiceFullSerializer
from billing.utils.invoice_service import *
from contract.models import ContractTerminationRequest

class ManageNewBudgetLineView(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Invoice.objects.all().order_by('-created_at')
    def post(self, request, *args, **kwargs):
        print("in manage new budget line view")
        invoice_id = request.data.get('invoice_id', None)
        line_item_type_id = request.data.get('line_item_type_id', None)
        
        invoice = None
        try:
            invoice = Invoice.objects.get(id=invoice_id)
        except Invoice.DoesNotExist:
            raise Exception("Invoice not found")
        
        try:
            line_item_type = LineItemType.objects.get(id=line_item_type_id)
        except LineItemType.DoesNotExist:
            raise Exception("Line item type not found")

        contract = None
        connection = None

        if invoice.contract:
            contract = invoice.contract
        elif invoice.contract_request:
            contract = invoice.contract_request
        elif invoice.contract_termination:
            contract = invoice.contract_termination.contract
        elif invoice.connection_request:
            connection = invoice.connection_request
        
        print("contract: ", contract)
        print("connection: ", connection)
        print("line_item_type: ", line_item_type)
        
        if contract:
            line_items = create_from_lineitemtype(contract, line_item_type, None, None, None)
        elif connection:
            line_items = create_from_lineitemtype_connection(connection, line_item_type, None)
        else:
            line_items = create_from_lineitemtype(None, line_item_type, None, None, None)
        
        # Handle case where line_items is None
        if line_items is None:
            line_items = []
        
        k = InvoiceLineItem.objects.filter(invoice=invoice, is_active=True).count()
        # Create temporary model instances from the dicts for proper serialization
        line_item_instances = []
        for line_item_dict in line_items:
            line_item_dict['token'] = f"{invoice.number}-{k}"
            line_item_dict['invoice'] = invoice
            # Create a temporary instance (not saved to DB) for serialization
            
            #ADDED THIS TO AVOID BREAKING BECAUSE OF ADJUSTMENT MODEL RELATION CHANGES. PLEASE REMOVE IT WHEN FIXED.
            adj_data = line_item_dict.pop('adjustments', None)
            
            line_item_instance = InvoiceLineItem(**line_item_dict)
            line_item_instances.append(line_item_instance)
            k += 1
        
        line_items_serialized = InvoiceLineItemSerializer(line_item_instances, many=True).data
        
        line_items_modified = [
            {
                **item,
                'company': item['company']['id'] if isinstance(item.get('company'), dict) else item.get('company'),
                'price_rate': item['price_rate']['id'] if isinstance(item.get('price_rate'), dict) else item.get('price_rate'),
                'tax': item['tax']['id'] if isinstance(item.get('tax'), dict) else item.get('tax'),
                'product': item['product']['id'] if isinstance(item.get('product'), dict) else item.get('product'),
            }
            for item in line_items_serialized
        ]

        return Response({'new_lines': line_items_modified}, status=status.HTTP_200_OK)