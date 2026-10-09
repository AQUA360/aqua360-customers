from django.db.models import Sum
from rest_framework import serializers
from billing.models import PaymentRemittance, PaymentStatus
from billing.serializers.payment_serializer import PaymentSerializer
from coredata.models import ConfigProject

class PaymentRemittanceSerializer(serializers.ModelSerializer):
    # payments = PaymentSerializer(many=True, read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    status_token = serializers.CharField(source='status.token', read_only=True)
    sent_by_username = serializers.CharField(source='sent_by.username', read_only=True)
    document_url = serializers.SerializerMethodField()
    document_name = serializers.CharField(source='document.document_name', read_only=True)
    document_service = serializers.CharField(source='document.service', read_only=True)
    document_location = serializers.CharField(source='document.location', read_only=True)
    company_bank_iban = serializers.CharField(source='company_bank.iban', read_only=True, default=None)
    total_payments = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    
    has_paid_payments = serializers.SerializerMethodField()
    has_non_direct_debit_payments = serializers.SerializerMethodField()
    
    class Meta:
        model = PaymentRemittance
        fields = '__all__'
    
    def get_fields(self):
        fields = super().get_fields()
        # Excloure payments de la resposta
        fields.pop('payments', None)
        return fields
    
    def get_has_paid_payments(self, obj):
        return obj.payments.filter(status=PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)).count() > 0
    
    def get_has_non_direct_debit_payments(self, obj):
        payment_type_token = "DIRECT_DEBIT" if not obj.is_return else "BANK_TRANSFER"
        return obj.payments.exclude(payment_type_token=payment_type_token).distinct().count() > 0
    
    def get_total_payments(self, obj):
        return obj.payments.count()
    
    def get_sent_by_username(self, obj):
        return obj.sent_by.username if obj.sent_by else None
    
    def get_document_url(self, obj):
        if obj.document:
            # Comprovar primer si hi ha un fitxer directe
            if obj.document.file:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(obj.document.file.url)
                else:
                    return obj.document.file.url
            # Si no hi ha fitxer directe, comprovar location_url
            elif obj.document.location_url:
                return obj.document.location_url
            # Si no hi ha location_url, retornar la ubicació si existeix
            elif obj.document.location:
                return obj.document.location
        return None
    
    def get_total_amount(self, obj):
        return obj.payments.aggregate(total_amount=Sum('amount'))['total_amount'] or 0
    

class PaymentRemittanceListSerializer(serializers.ModelSerializer):
    status_name = serializers.CharField(source='status.name')
    status_color = serializers.CharField(source='status.color')
    status_token = serializers.CharField(source='status.token')
    sent_by_username = serializers.SerializerMethodField()
    total_payments = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    company_bank_iban = serializers.CharField(source='company_bank.iban', read_only=True, default=None)
    
    class Meta:
        model = PaymentRemittance
        fields = [
            'id', 'token', 'created_at', 
            'updated_at', 'status_name', 'status_color',
            'total_payments', 'sent_at', 'sent_by_username',
            'status_token', 'document', 'desired_send_at',
            'total_amount', 'is_return', 'company_bank', 'company_bank_iban'
        ]
    
    def get_total_amount(self, obj):
        return obj.payments.aggregate(total_amount=Sum('amount'))['total_amount'] or 0
    
    def get_total_payments(self, obj):
        return obj.payments.count()
    
    def get_sent_by_username(self, obj):
        return obj.sent_by.username if obj.sent_by else None