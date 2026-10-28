from rest_framework import serializers
from django_filters import rest_framework as filters

from documentmanager.serializers import DocumentSerializer
from ..models import ( ContractStatus, ContractSurrogationDocumentType, ContractTenantChangeDocumentType, ContractUseType, ContractClientType, ContractCategory, ContractRequest, ContractRequestStatus, ContractRequestType, ContractRequestDocumentation, BonificationTypeDocumentationType, ContractRepresentativeType, VariableType, ContractRequestDocumentationType, PaymentType, ContractTerminationStatus, ContractTerminationType, ContractSurrogationType, BailType, BailStatus, ContractDebtManagement, ContractDocumentationType)

class ContractStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractStatus
        fields = '__all__'

class ContractUseTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractUseType
        fields = '__all__'

class ContractClientTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractClientType
        fields = '__all__'

class ContractCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractCategory
        fields = '__all__'

class ContractRequestStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractRequestStatus
        fields = '__all__'

class ContractRequestTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractRequestType
        fields = '__all__'

class BonificationTypeDocumentationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BonificationTypeDocumentationType
        fields = '__all__'

class ContractRepresentativeTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractRepresentativeType
        fields = '__all__'

class VariableTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VariableType
        fields = '__all__'

class ContractRequestDocumentationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractRequestDocumentationType
        fields = '__all__'
        
class ContractDocumentationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractDocumentationType
        fields = '__all__'

class PaymentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentType
        fields = '__all__'

class ContractTerminationRequestStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractTerminationStatus
        fields = '__all__'

class ContractTerminationRequestTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractTerminationType
        fields = '__all__'

    def update(self, instance, validated_data):
        was_change_of_name = instance.is_change_of_name
        instance = super().update(instance, validated_data)
        # En marcar el tipus, les sol·licituds ja vinculades a baixes d'aquest tipus passen a ser
        # canvis de nom. Es fa amb update() per no tornar a assignar-los tarifes ni ordres.
        if instance.is_change_of_name and not was_change_of_name:
            ContractRequest.objects.filter(
                contract_termination_requests__type=instance, is_change_of_name=False,
            ).update(is_change_of_name=True)
        return instance

class ContractSurrogationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractSurrogationType
        fields = '__all__'

class BailTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BailType
        fields = '__all__'


class BailStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = BailStatus
        fields = '__all__'
        
class ContractSurrogationDocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractSurrogationDocumentType
        fields = '__all__'
        
class ContractTenantChangeDocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractTenantChangeDocumentType
        fields = '__all__'

class ContractRequestDocumentationSerializer(serializers.ModelSerializer):
    type = ContractRequestDocumentationTypeSerializer(required=False, allow_null=True)
    contract_type = ContractDocumentationTypeSerializer(required=False, allow_null=True)
    file = DocumentSerializer(read_only=True, required=False, allow_null=True)
    class Meta:
        model = ContractRequestDocumentation
        fields = '__all__'

class ContractRequestDocumentationSaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractRequestDocumentation
        fields = '__all__'

class ContractDebtManagementSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractDebtManagement
        fields = '__all__'