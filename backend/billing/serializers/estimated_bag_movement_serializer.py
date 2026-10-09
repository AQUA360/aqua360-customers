from rest_framework import serializers


from ..models import ( EstimatedBagMovement )

class EstimatedBagMovementSerializer(serializers.ModelSerializer):
    reading = serializers.SerializerMethodField()
    invoice = serializers.SerializerMethodField()
    
    class Meta:
        model = EstimatedBagMovement
        fields = '__all__'
    
    def get_reading(self, obj):
        from billing.serializers.reading_serializer import ReadingMinimalSerializer
        if obj.reading:
            return ReadingMinimalSerializer(obj.reading).data
        return None
    
    def get_invoice(self, obj):
        from billing.serializers.invoice_serializer import InvoiceMinimalSerializer
        if obj.invoice:
            return { 'id': obj.invoice.id, 'token': obj.invoice.token }
        return None


class EstimatedBagMovementMinimalSerializer(serializers.ModelSerializer):
    estimated_bag_token = serializers.CharField(source='estimated_bag.token', read_only=True)
    estimated_bag_id = serializers.IntegerField(source='estimated_bag.id', read_only=True)
    reading_token = serializers.CharField(source='reading.token', read_only=True)
    reading_id = serializers.IntegerField(source='reading.id', read_only=True)
    
    class Meta:
        model = EstimatedBagMovement
        fields = ['id', 'token', 'amount', 'is_positive', 'estimated_bag_token', 'estimated_bag_id', 'reading_token', 'reading_id']