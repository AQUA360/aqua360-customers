from rest_framework import serializers
from auth.serializers import UserMinimalSerializer
from verifactu.models import VerifactuBatch, VerifactuNotification, VerifactuNotificationLog


class VerifactuNotificationSerializer(serializers.ModelSerializer):
    invoice_id = serializers.SerializerMethodField()
    invoice_token = serializers.SerializerMethodField()
    
    class Meta:
        model = VerifactuNotification
        fields = '__all__'
    
    def get_invoice_id(self, obj):
        invoice = obj.invoice_set.first()
        return invoice.id if invoice else None
    
    def get_invoice_token(self, obj):
        invoice = obj.invoice_set.first()
        return invoice.token if invoice else None
class VerifactuBatchSerializer(serializers.ModelSerializer):
    verifactu_notifications_count = serializers.SerializerMethodField()
    
    class Meta:
        model = VerifactuBatch
        fields = '__all__'
    
    def get_verifactu_invoices_count(self, obj):
        return obj.verifactu_notifications.count()


class VerifactuNotificationLogSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(read_only=True)
    
    class Meta:
        model = VerifactuNotificationLog
        fields = [
            'id',
            'created_at',
            'field_name',
            'old_value',
            'new_value',
            'operation_token',
            'user'
        ]