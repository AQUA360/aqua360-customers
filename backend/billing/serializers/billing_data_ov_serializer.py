from rest_framework import serializers
from contract.models import Contract

class BillingDataOVSerializer(serializers.ModelSerializer):
    nif = serializers.CharField(source='holder.token', read_only=True)
    tenant_name = serializers.SerializerMethodField()
    holder_name = serializers.SerializerMethodField()
    supply_point_address = serializers.SerializerMethodField()
    city = serializers.CharField(source='supply_point_default.address.city.name', read_only=True)
    postal_code = serializers.CharField(source='supply_point_default.address.postal_code', read_only=True)
    paper_invoice = serializers.SerializerMethodField()
    email = serializers.CharField(source='person_contact_email.email', read_only=True)
    invoice_language = serializers.SerializerMethodField()
    phone1 = serializers.SerializerMethodField()
    phone2 = serializers.SerializerMethodField()
    payment_type = serializers.CharField(source='payment.type.token', read_only=True)
    iban = serializers.CharField(source='payment.IBAN.iban', read_only=True)
    
    class Meta:
        model = Contract
        fields = ['nif', 'tenant_name', 'holder_name', 'supply_point_address', 'city', 
                  'postal_code', 'paper_invoice', 'email', 'invoice_language', 'phone1', 
                  'phone2', 'payment_type', 'iban']
    
    def get_tenant_name(self, obj):
        return f'{obj.holder.name} {obj.holder.surname}'
    
    def get_holder_name(self, obj):
        return f'{obj.holder.name} {obj.holder.surname}'
    
    def get_supply_point_address(self, obj):
        supply_point = obj.supply_point_default
        if supply_point:
            return str(supply_point.address)
        return None
    
    def get_phone1(self, obj):
        contact = obj.contacts.filter(is_default=True).first()
        if contact:
            return contact.phone
        return ''
    
    def get_phone2(self, obj):
        contact = obj.contacts.filter(is_default=False).first()
        if contact:
            return contact.phone
        return ''
    
    def get_paper_invoice(self, obj):
        communication_type = obj.communication_type
        return 'true' if communication_type != 'DIGITAL' else ''
    
    def get_invoice_language(self, obj):
        return 'ca'