from rest_framework import serializers
from django_filters import rest_framework as filters
from ..models import *

class InvoiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceType
        fields = '__all__'

class InvoiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceCategory
        fields = '__all__'

class InvoiceSerieSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceSerie
        fields = '__all__'

class InvoiceSequenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceSequence
        fields = '__all__'
    
class PaymentStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentStatus
        fields = '__all__'
class PaymentStatusMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentStatus
        fields = [
            'id', 'token', 'name', 'color'
            ]
        
class InvoiceStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceStatus
        fields = '__all__'
class InvoiceWarningSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceWarning
        fields = '__all__'
        
class RejectMotiveSerializer(serializers.ModelSerializer):
    class Meta:
        model = RejectMotive
        fields = '__all__'
        
class RejectMotiveTypeSerializer(serializers.ModelSerializer):
    
    rejects = RejectMotiveSerializer(many=True, read_only=True)
    
    class Meta:
        model = RejectMotiveType
        fields = '__all__'

class InvoiceClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceClass
        fields = '__all__'

class ReadingAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingAlert
        fields = '__all__'

class CommitmentDepositStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommitmentDepositStatus
        fields = '__all__'

class PaymentCommitmentStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentCommitmentStatus
        fields = '__all__'

class PaymentRemittanceStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentRemittanceStatus
        fields = '__all__'

class InvoiceSuppressionReasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceSuppressionReason
        fields = '__all__'

class RemoteReadingAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = RemoteReadingAlert
        fields = '__all__'

class BankRNDDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankRNDDocument
        fields = '__all__'
    
class JoinedPaymentStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = JoinedPaymentStatus
        fields = '__all__'
