from rest_framework import serializers

from billing.models import InvoiceLineItem
from billing.utils.invoice_service import update_invoice_totals
from billing.utils.invoice_line_item_service import constrain_total_value
from coredata.models import ConfigProject
from coredata.utils.other_utils import round_ceil
from pricing.serializers.line_item_type_serializer import LineItemTypeMinimalSerializer
from pricing.serializers.price_rate_serializer import PriceRateMinimalSerializer
from pricing.serializers.value_objects_serializer import TaxSerializer
from pricing.utils.tax_service import resolve_tax_for_line_item
from service.serializers.company_serializer import CompanySerializer

class InvoiceLineItemSerializer(serializers.ModelSerializer):
    
    company = CompanySerializer(read_only=True, required=False, allow_null=True)
    line_item_type = LineItemTypeMinimalSerializer(read_only=True, required=False, allow_null=True)
    price_rate = PriceRateMinimalSerializer(read_only=True, required=False, allow_null=True)
    tax = TaxSerializer(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = InvoiceLineItem
        fields = '__all__'
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        # InvoiceLineItem has a direct product field
        if instance.custom_order:
            data['product_order'] = instance.custom_order
        else:
            data['product_order'] = instance.product.order_priority if instance.product and instance.product.order_priority else ""
        return data

class InvoiceLineItemSaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLineItem
        fields = '__all__'
        
    def create(self, validated_data):
        invoice_type_token = ConfigProject.objects.get(token='invoice_type_invoice_token').value
        total = validated_data.get('total', 0.00)
        price = validated_data.get('price', 0.00)
        tax_price = validated_data.get('tax_price', 0.00)
        validated_data['price'] = round_ceil(price) if price else 0.00
        validated_data['tax_price'] = round_ceil(tax_price) if tax_price else 0.00
        validated_data['total'] = round_ceil(total) if total else 0.00
        if validated_data.get('tax_percent', None) is not None:
            validated_data['tax'] = resolve_tax_for_line_item(validated_data)
        if not total:
            if price != None and tax_price != None:
                total = float(price) + float(tax_price)
        # Constrain total to database field limits (max_digits=10, decimal_places=4)
        if total is not None:
            total = constrain_total_value(total)
            validated_data['total'] = total
            
        # ADDED THIS TO AVOID BREAKING BECAUSE OF ADJUSTMENT MODEL RELATION CHANGES. PLEASE REMOVE IT WHEN FIXED.
        adjustments = validated_data.pop('adjustments', None)
        print("adjustments: ", adjustments)
            
        lineItem = InvoiceLineItem.objects.create(**validated_data)
        update_invoice_totals(lineItem.invoice)
        lineItem.invoice.manually_modified = lineItem.invoice.type.token == invoice_type_token
        lineItem.invoice.save()
        return lineItem
    
    def update(self, instance, validated_data):
        invoice_type_token = ConfigProject.objects.get(token='invoice_type_invoice_token').value
        
        price = validated_data.pop('price', 0.00)
        tax_price = validated_data.pop('tax_price', 0.00)
        total = validated_data.pop('total', 0.00)
        
        validated_data['price'] = round_ceil(price) if price else 0.00
        validated_data['tax_price'] = round_ceil(tax_price) if tax_price else 0.00
        validated_data['total'] = round_ceil(total) if total else 0.00
        
        if instance.invoice.type.token != invoice_type_token:
            validated_data.pop('manually_modified', None)
            validated_data.pop('manually_added', None)
        
        if validated_data.get('tax_percent', None) is not None:
            validated_data['tax'] = resolve_tax_for_line_item(validated_data)
        total = validated_data.get('total', None)
        if not total:
            if price and tax_price:
                total = round_ceil(float(price) + float(tax_price))
        # Constrain total to database field limits (max_digits=10, decimal_places=4)
        if total is not None:
            total = constrain_total_value(total)
            validated_data['total'] = total
        else:
            pre_total = tax_price + price
            total = constrain_total_value(pre_total)
            validated_data['total'] = total
            
        # ADDED THIS TO AVOID BREAKING BECAUSE OF ADJUSTMENT MODEL RELATION CHANGES. PLEASE REMOVE IT WHEN FIXED.
        adjustments = validated_data.pop('adjustments', None)
        print("adjustments: ", adjustments)
        
        instance = super().update(instance, validated_data)
        update_invoice_totals(instance.invoice)
        instance.invoice.manually_modified = instance.invoice.type.token == invoice_type_token
        instance.invoice.save()
        return instance