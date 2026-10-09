from rest_framework import serializers
from billing.serializers.invoice_serializer import InvoiceMinimalSerializer
from billing.serializers.payment_serializer import PaymentSerializer
from billing.serializers.value_objects_serializer import InvoiceStatusSerializer, JoinedPaymentStatusSerializer, PaymentStatusSerializer
from claimrequest.serializers.claim_request_status_serializer import ClaimRequestStatusSerializer
from billing.serializers.payment_commitment_serializer import PaymentCommitmentSerializer
from billing.serializers.value_objects_serializer import CommitmentDepositStatusSerializer, InvoiceStatusSerializer
from communication.serializers.value_objects_serializer import CommunicationProcessStatusSerializer, CommunicationStatusSerializer, CommunicationUseTypeSerializer, MessageTypeSerializer
from contract.serializers.bonification_serializer import BonificationSerializer
from contract.serializers.contract_serializer import ContractMinimalSerializer, ContractSerializer
from contract.serializers.value_objects_serializer import ContractDebtManagementSerializer, ContractRequestStatusSerializer
from contract.serializers.variable_serializer import VariableSerializer
from contract.models import ContractDataChange
from fraud.serializers.value_objects_serializer import FraudStatusSerializer
from notification.serializers.value_objects_serializer import IncidentStatusSerializer
from service.models import SupplyPointStatus
from service.serializers.supply_point_serializer import SupplyPointSerializer
from service.serializers.value_objects_serializer import SupplyCutStatusSerializer

from .models import *
from service.serializers.value_objects_serializer import ConnectionStatusSerializer, ConnectionRequestStatusSerializer
from service.serializers.supply_point_serializer import SupplyPointMinimalSerializer

from auth.serializers import UserMinimalSerializer

class LogConnectionStatusSerializer(serializers.ModelSerializer):
    previous_status = ConnectionStatusSerializer(required=False, allow_null=True)
    current_status = ConnectionStatusSerializer(required=False, allow_null=True)
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = LogConnectionStatus
        fields = '__all__'
        
class LogConnectionRequestStatusSerializer(serializers.ModelSerializer):
    previous_status = ConnectionRequestStatusSerializer(required=False, allow_null=True)
    current_status = ConnectionRequestStatusSerializer(required=False, allow_null=True)
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = LogConnectionRequestStatus
        fields = '__all__'

class LogSupplyCutStatusSerializer(serializers.ModelSerializer):
    previous_status = SupplyCutStatusSerializer(required=False, allow_null=True)
    current_status = SupplyCutStatusSerializer(required=False, allow_null=True)
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = LogSupplyCutStatus
        fields = '__all__'


class LogSupplyPointChangeSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)
    supply_point = SupplyPointMinimalSerializer(required=False, allow_null=True)
    
    class Meta:
        model = LogSupplyPointChange
        fields = '__all__'

    def to_representation(self, instance):
        # Obtenim la representació per defecte
        representation = super().to_representation(instance)

        # Comprovem si field_changed és 'status'
        if instance.field_changed == 'status':
            # Inicialitzem els valors per defecte
            previous_status = None
            current_status = None

            # Obtenim el previous_status si previous_related_id és vàlid
            if instance.previous_related_id:
                try:
                    previous_status_obj = SupplyPointStatus.objects.get(id=instance.previous_related_id)
                    previous_status = {
                        'id': previous_status_obj.id,
                        'name': previous_status_obj.name,
                        'token': previous_status_obj.token,
                    }
                except SupplyPointStatus.DoesNotExist:
                    previous_status = None
            representation['previous_status'] = previous_status

            # Obtenim el current_status si current_related_id és vàlid
            if instance.current_related_id:
                try:
                    current_status_obj = SupplyPointStatus.objects.get(id=instance.current_related_id)
                    current_status = {
                        'id': current_status_obj.id,
                        'name': current_status_obj.name,
                        'token': current_status_obj.token,
                    }
                except SupplyPointStatus.DoesNotExist:
                    current_status = None
            representation['current_status'] = current_status
        else:
            # Si field_changed no és 'status', assegurem que aquests camps no apareguin
            representation.pop('previous_status', None)
            representation.pop('current_status', None)

        return representation

class LogContractRequestStatusSerializer(serializers.ModelSerializer):
    previous_status = ContractRequestStatusSerializer(required=False, allow_null=True)
    current_status = ContractRequestStatusSerializer(required=False, allow_null=True)
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = LogContractRequestStatus
        fields = '__all__'


class LogOrderStatusSerializer(serializers.ModelSerializer):
    previous_status = serializers.CharField(required=False, allow_null=True)
    current_status = serializers.CharField(required=False, allow_null=True)
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = LogOrderStatus
        fields = '__all__'

class LogBailStatusSerializer(serializers.ModelSerializer):
    previous_status = serializers.CharField(required=False, allow_null=True)
    current_status = serializers.CharField(required=False, allow_null=True)
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = LogBailStatus
        fields = '__all__'

class LogContractTotalMembersSerializer(serializers.ModelSerializer):
    previous_total_persons = serializers.IntegerField(required=False, allow_null=True)
    current_total_persons = serializers.IntegerField(required=False, allow_null=True)
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = LogContractTotalMembers
        fields = '__all__'


class LogContractPhonesSerializer(serializers.ModelSerializer):
    previous_phone = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    current_phone = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    user = UserMinimalSerializer(required=False, allow_null=True)

    class Meta:
        model = LogContractPhones
        fields = '__all__'


class LogContractBonificationsVariablesChangeSerializer(serializers.ModelSerializer):
    previous_bonification = BonificationSerializer(required=False, allow_null=True)
    current_bonification = BonificationSerializer(required=False, allow_null=True)
    previous_variable = VariableSerializer(required=False, allow_null=True)
    current_variable = VariableSerializer(required=False, allow_null=True)
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = LogContractBonificationsVariablesChange
        fields = '__all__'

class LogContractExpiredBonificationsVariablesSerializer(serializers.ModelSerializer):
    expired_bonification = BonificationSerializer(required=False, allow_null=True)
    expired_variable = VariableSerializer(required=False, allow_null=True)
    class Meta:
        model = LogContractExpiredBonificationsVariables
        fields = '__all__'

class LogClaimRequestContractChangeSerializer(serializers.ModelSerializer):
    deleted_contract = ContractMinimalSerializer(required=False, allow_null=True)
    current_debt_management = ContractDebtManagementSerializer(required=False, allow_null=True)
    previous_status = ClaimRequestStatusSerializer(required=False, allow_null=True)
    current_status = ClaimRequestStatusSerializer(required=False, allow_null=True)
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = LogClaimRequestContractChange
        fields = '__all__'

class LogInvoiceChangeStatusSerializer(serializers.ModelSerializer):
    previous_status = InvoiceStatusSerializer(required=False, allow_null=True)
    current_status = InvoiceStatusSerializer(required=False, allow_null=True)
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = LogInvoiceChangeStatus
        fields = '__all__'

class LogCommitmentDepositMovementSerializer(serializers.ModelSerializer):
    previous_status = CommitmentDepositStatusSerializer(required=False, allow_null=True)
    current_status = CommitmentDepositStatusSerializer(required=False, allow_null=True)
    new_payment = PaymentCommitmentSerializer(required=False, allow_null=True)
    new_invoices = InvoiceMinimalSerializer(required=False, many=True, allow_null=True)
    paid_invoice = InvoiceMinimalSerializer(required=False, allow_null=True)
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = LogCommitmentDepositMovement
        fields = '__all__'

class LogCommitmentDepositMovementSerializer(serializers.ModelSerializer):
    previous_status = CommitmentDepositStatusSerializer(required=False, allow_null=True)
    current_status = CommitmentDepositStatusSerializer(required=False, allow_null=True)
    new_payment = PaymentCommitmentSerializer(required=False, allow_null=True)
    new_wallet = PaymentSerializer(required=False, allow_null=True)
    new_invoices = InvoiceMinimalSerializer(required=False, many=True, allow_null=True)
    paid_invoice = InvoiceMinimalSerializer(required=False, allow_null=True)
    paid_invoice_payment = PaymentSerializer(required=False, allow_null=True)
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = LogCommitmentDepositMovement
        fields = '__all__'

class LogPaymentStatusChangeSerializer(serializers.ModelSerializer):
    previous_status = PaymentStatusSerializer(required=False, allow_null=True)
    current_status = PaymentStatusSerializer(required=False, allow_null=True)
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = LogPaymentStatusChange
        fields = '__all__'

class LogFraudStatusChangeSerializer(serializers.ModelSerializer):
    previous_status = FraudStatusSerializer(required=False, allow_null=True)
    current_status = FraudStatusSerializer(required=False, allow_null=True)
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = LogFraudStatusChange
        fields = '__all__'
    
class LogIncidentStatusChangeSerializer(serializers.ModelSerializer):
    previous_status = IncidentStatusSerializer(required=False, allow_null=True)
    current_status = IncidentStatusSerializer(required=False, allow_null=True)
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = LogIncidentStatusChange
        fields = '__all__'

class LogCommunicationStatusChangeSerializer(serializers.ModelSerializer):
    previous_status = CommunicationStatusSerializer(required=False, allow_null=True)
    current_status = CommunicationStatusSerializer(required=False, allow_null=True)
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = LogCommunicationStatusChange
        fields = '__all__'

class LogCommunicationProcessStatusChangeSerializer(serializers.ModelSerializer):
    previous_status = CommunicationProcessStatusSerializer(required=False, allow_null=True)
    current_status = CommunicationProcessStatusSerializer(required=False, allow_null=True)
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = LogCommunicationProcessStatusChange
        fields = '__all__'

class LogInvoiceDataChangeSerializer(serializers.ModelSerializer):
    previous_address = serializers.CharField(required=False, allow_null=True)
    current_address = serializers.CharField(required=False, allow_null=True)
    previous_payment_type = serializers.CharField(required=False, allow_null=True)
    current_payment_type = serializers.CharField(required=False, allow_null=True)
    previous_iban = serializers.CharField(required=False, allow_null=True)
    current_iban = serializers.CharField(required=False, allow_null=True)
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = LogInvoiceDataChange
        fields = '__all__'


class LogContractDataChangeSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)
    previous_address = serializers.SerializerMethodField()
    current_address = serializers.SerializerMethodField()
    previous_payment_type = serializers.SerializerMethodField()
    current_payment_type = serializers.SerializerMethodField()
    previous_iban = serializers.SerializerMethodField()
    current_iban = serializers.SerializerMethodField()
    timestamp = serializers.SerializerMethodField()

    class Meta:
        model = ContractDataChange
        fields = [
            'id', 'user', 'timestamp', 'approved_at',
            'previous_address', 'current_address',
            'previous_payment_type', 'current_payment_type',
            'previous_iban', 'current_iban'
        ]

    def get_timestamp(self, obj):
        ts = obj.approved_at or obj.created_at
        return ts.isoformat() if ts else None

    def get_previous_address(self, obj):
        if obj.previous_address_billing and obj.previous_address_billing.address:
            return str(obj.previous_address_billing.address)
        return None

    def get_current_address(self, obj):
        if obj.new_address_billing and obj.new_address_billing.address:
            return str(obj.new_address_billing.address)
        return None

    def get_previous_payment_type(self, obj):
        if obj.previous_payment_type:
            return obj.previous_payment_type.name or obj.previous_payment_type.token
        return None

    def get_current_payment_type(self, obj):
        if obj.new_payment_type:
            return obj.new_payment_type.name or obj.new_payment_type.token
        return None

    def get_previous_iban(self, obj):
        if obj.previous_payment:
            return obj.previous_payment.iban
        return None

    def get_current_iban(self, obj):
        if obj.new_payment:
            return obj.new_payment.iban
        return None


class LogReadingChangeSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)
    contract = ContractMinimalSerializer(required=False, allow_null=True)

    class Meta:
        model = LogReadingChange
        fields = '__all__'


class LogJoinedPaymentStatusChangeSerializer(serializers.ModelSerializer):
    previous_status = JoinedPaymentStatusSerializer(required=False, allow_null=True)
    current_status = JoinedPaymentStatusSerializer(required=False, allow_null=True)
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = LogJoinedPaymentStatusChange
        fields = '__all__'

class LogCommunicationChangeSerializer(serializers.ModelSerializer):
    previous_types = MessageTypeSerializer(required=False, many=True, allow_null=True)
    current_types = MessageTypeSerializer(required=False, many=True, allow_null=True)
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = LogCommunicationChange
        fields = '__all__'

class LogProductChangeSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)
    
    class Meta:
        model = LogProductChange
        fields = '__all__'

class LogPriceRateChangeSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)
    
    class Meta:
        model = LogPriceRateChange
        fields = '__all__'
