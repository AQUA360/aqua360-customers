from rest_framework import serializers

from billing.models import CommitmentDeposit, Payment, PaymentRemittance, PaymentStatus
from billing.serializers.commitment_deposit_serializer import CommitmentDepositSerializer
from billing.serializers.invoice_serializer import InvoiceMinimalSerializer
from billing.serializers.value_objects_serializer import PaymentStatusSerializer, PaymentStatusMinimalSerializer, RejectMotiveSerializer
from billing.utils.commitment_deposit_service import update_deposit
from billing.utils.payment_service import disconnect_payment_signals, reconnect_payment_signals
from contract.serializers.contract_minimal_serializer import ContractMinimalSerializer
from coredata.models import ConfigProject
from documentmanager.serializers import DocumentSerializer

class PaymentListSerializer(serializers.ModelSerializer):
    
    status = PaymentStatusSerializer(read_only=True, required=False, allow_null=True)
    invoice = serializers.SerializerMethodField()
    commitment_deposit = serializers.SerializerMethodField()
    reject = RejectMotiveSerializer(read_only=True, required=False, allow_null=True)

    payment_origin = serializers.CharField(read_only=True, required=False, allow_null=True)

    class Meta:
        model = Payment
        fields = ['id', 'token', 'status', 'name', 'due_date', 'amount', 'is_excluded', 'payment_type', 'payment_origin', 'payment_date', 'invoice', 'commitment_deposit', 'reject']
    
    def get_invoice(self, obj):
        if obj.invoice:
            return {
                'id': obj.invoice.id,
                'token': obj.invoice.token,
                'serie_final': obj.invoice.serie_final,
            }
        return None
    
    
    def get_commitment_deposit(self, obj):
        if obj.commitment_deposit:
            return {
                'id': obj.commitment_deposit.id,
                'token': obj.commitment_deposit.token,
            }
        return None

class PaymentSerializer(serializers.ModelSerializer):
    
    invoice = InvoiceMinimalSerializer(read_only=True, required=False, allow_null=True)
    status = PaymentStatusSerializer(read_only=True, required=False, allow_null=True)
    reject = RejectMotiveSerializer(read_only=True, required=False, allow_null=True)
    commitment_deposit = CommitmentDepositSerializer(read_only=True, required=False, allow_null=True)
    document = DocumentSerializer(read_only=True, required=False, allow_null=True)
    contract = ContractMinimalSerializer(read_only=True, required=False, allow_null=True)
    remittances = serializers.SerializerMethodField()
    joined_payments = serializers.SerializerMethodField()
    
    payment_origin = serializers.CharField(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Payment
        fields = '__all__'
    
    def get_remittances(self, obj):
        remittances = PaymentRemittance.objects.filter(payments=obj).order_by('-created_at')
        rem_data = []
        for remittance in remittances:
            rem_data.append({
                'id': remittance.id,
                'created_at': remittance.created_at,
                'token': remittance.token,
                'sent_at': remittance.sent_at,
                'sent_by': remittance.sent_by.username if remittance.sent_by else None
            })
        return rem_data
    
    def get_joined_payments(self, obj):
        joined_payments = obj.joined_payments.all()
        status_paid_token = ConfigProject.objects.get(token="joined_payment_status_paid_token").value
        status_cancel_token = ConfigProject.objects.get(token="joined_payment_status_cancelled_token").value
        joined_data = []
        for joined_payment in joined_payments:
            joined_data.append({
                'id': joined_payment.id,
                'token': joined_payment.token,
                'status_name': joined_payment.status.name,
                'status_color': joined_payment.status.color,
                'payment_type': joined_payment.payment_type.name,
                'payment_date': joined_payment.payment_date,
                'due_date': joined_payment.due_date,
                'total_final': joined_payment.total_final,
                'allow_change': joined_payment.status.token == status_paid_token or joined_payment.status.token == status_cancel_token 
            })
        return joined_data

class PaymentSaveSerializer(serializers.ModelSerializer):
    
    status_token = serializers.CharField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Payment
        fields = '__all__'
    
    def create(self, validated_data):
        print("create payment")
        status_token = validated_data.pop('status_token', None)
        if status_token:
            validated_data['status'] = PaymentStatus.objects.get(token=status_token)
        return super(PaymentSaveSerializer, self).create(validated_data)
    
    def update(self, instance, validated_data):
        print("update payment")
        status_token = validated_data.pop('status_token', None)
        due_date = validated_data.pop('due_date', None)
        if 'is_excluded' in validated_data and not status_token:
            disconnect_payment_signals()
        if due_date:
            instance.due_date = due_date
            invoice = instance.invoice
            if invoice.due_date < due_date:
                invoice.due_date = due_date
                invoice._skip_signal = True
                invoice.save()
        
        if status_token:
            instance.status = PaymentStatus.objects.get(token=status_token)
            
        
        if validated_data.get('is_excluded') != None:
            instance.is_excluded = validated_data.get('is_excluded')
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        update_deposit(instance)
        reconnect_payment_signals()
        return instance

class PaymentMinimalSerializer(serializers.ModelSerializer):
    
    invoice_id = serializers.IntegerField(source='invoice.id', read_only=True)
    commitment_deposit_id = serializers.IntegerField(source='commitment_deposit.id', read_only=True)
    invoice_token = serializers.CharField(source='invoice.token', read_only=True)
    invoice_serie_final = serializers.CharField(source='invoice.serie_final', read_only=True)
    invoice_status_name = serializers.CharField(source='invoice.status.name', read_only=True)
    invoice_status_color = serializers.CharField(source='invoice.status.color', read_only=True)
    status = PaymentStatusMinimalSerializer(read_only=True, required=False, allow_null=True)
    contract_id = serializers.IntegerField(source='invoice.contract.id', read_only=True)
    contract_token = serializers.CharField(source='invoice.contract.token', read_only=True)
    
    payment_origin = serializers.CharField(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'token', 'status',
            'invoice_id', 'invoice_token', 'commitment_deposit_id', 'due_date',
            'amount', 'contract_id', 'contract_token',
            'payment_type', 'payment_origin', 'invoice_serie_final',
            'invoice_status_name', 'invoice_status_color'
            ]

class PaymentSEPASerializer(serializers.ModelSerializer):
    status = PaymentStatusMinimalSerializer(read_only=True, required=False, allow_null=True)
    invoice = serializers.SerializerMethodField()
    contract = serializers.SerializerMethodField()
    person = serializers.SerializerMethodField()
    commitment_deposit = serializers.SerializerMethodField()
    reject_name = serializers.CharField(source='reject.name', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'token', 'status',
            'invoice', 'commitment_deposit', 'due_date',
            'amount', 'is_excluded', 'payment_bank',
            'payment_date', 'payment_type_token', 'payment_type',
            'customer_final', 'customer_token_final', 'contract',
            'reject_name', 'person'
            ]
    
    def get_invoice(self, obj):
        if obj.invoice:
            return {
                'id': obj.invoice.id,
                'token': obj.invoice.serie_final,
                'due_date': obj.invoice.due_date,
                'customer_final': obj.invoice.customer_final,
                'customer_token_final': obj.invoice.customer_token_final,
            }
        return None
    
    def get_person(self, obj):
        if obj.person:
            return {
                'id': obj.person.id,
                'token': obj.person.token,
                'name': str(obj.person),
            }
        return None

    def get_contract(self, obj):
        contract = obj.invoice.contract if obj.invoice else obj.commitment_deposit.contract if obj.commitment_deposit else obj.contract
        if contract:
            return {
                'id': contract.id,
                'token': contract.token,
            }
        return None
    
    def get_commitment_deposit(self, obj):
        if obj.commitment_deposit:
            return {
            'id': obj.commitment_deposit.id,
            'token': obj.commitment_deposit.token,
            'due_date': obj.commitment_deposit.due_date,
            'customer_final': obj.commitment_deposit.customer_final,
            'customer_token_final': obj.commitment_deposit.customer_token_final,
            }
        return None

class ContractPaymentSerializer(serializers.ModelSerializer):
    status = PaymentStatusSerializer(read_only=True)
    invoice_id = serializers.IntegerField(source='invoice.id')
    invoice_token = serializers.CharField(source='invoice.token')
    
    class Meta:
        model = Payment
        fields = ['id', 'token', 'status', 'invoice_id', 'invoice_token', 'due_date', 'amount']