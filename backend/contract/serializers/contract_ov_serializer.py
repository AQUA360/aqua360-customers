from rest_framework import serializers
from contract.models import Contract

class ContractSerializer(serializers.ModelSerializer):
    status_token = serializers.CharField(source='status.token', read_only=True)
    holder_token = serializers.CharField(source='holder.token', read_only=True)
    payment_type = serializers.CharField(source='payment.type.token', read_only=True)
    last_invoice_date = serializers.SerializerMethodField()
    iban = serializers.CharField(source='payment.IBAN.iban', read_only=True)
    supply_point_address = serializers.SerializerMethodField()
    meter_serial_number = serializers.CharField(source='supply_point_default.meter.token', read_only=True)
    meter_caliber = serializers.CharField(source='supply_point_default.meter.caliber.name', read_only=True)
    smart_metering = serializers.SerializerMethodField()
    
    class Meta:
        model = Contract
        fields = ['token', 'status_token', 'holder_token', 'payment_type', 
                  'last_invoice_date', 'iban', 'supply_point_address', 
                  'meter_serial_number', 'meter_caliber', 'smart_metering']
        
    def get_last_invoice_date(self, obj):
        last_invoice = obj.invoices.order_by('-created_at').first()
        if last_invoice:
            return last_invoice.created_at
        return None
    
    def get_supply_point_address(self, obj):
        supply_point = obj.supply_point_default
        if supply_point:
            return str(supply_point.address)
        return None
    
    def get_smart_metering(self, obj):
        return 'true' if obj.supply_point_default.meter.comm_module else ''