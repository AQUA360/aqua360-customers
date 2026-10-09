import datetime
import uuid
from rest_framework import serializers

from auth.serializers import UserMinimalSerializer
from billing.serializers.value_objects_serializer import CommitmentDepositStatusSerializer
from billing.utils.payment_service import log_payment_status
from coredata.models import ConfigProject
from logger.models import LogCommitmentDepositMovement
from ..models import *
from coredata.serializers import PersonSerializer

class CommitmentDepositObservationSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)
    
    class Meta:
        model = CommitmentDepositObservation
        fields = '__all__'

class CommitmentDepositSerializer(serializers.ModelSerializer):
    
    status = CommitmentDepositStatusSerializer(read_only=True, required=False, allow_null=True)
    invoices = serializers.SerializerMethodField()
    contract = serializers.SerializerMethodField()
    usable_remaining = serializers.SerializerMethodField()
    contract_piggy_bank = serializers.SerializerMethodField()
    
    incidents = serializers.SerializerMethodField()
    remittances = serializers.SerializerMethodField()
    joined_payments = serializers.SerializerMethodField()
    
    class Meta:
        model = CommitmentDeposit
        fields = '__all__'
    
    def to_representation(self, instance):
        pending_status_token = ConfigProject.objects.get(token='payment_commitment_status_pending_token').value
        
        representation = super().to_representation(instance)
        representation['holder'] = instance.contract.holder.id if instance.contract and instance.contract.holder else None
        print("instance.contract: ", instance.contract)
        if instance.contract and instance.contract.tenant:
            representation['tenant'] = instance.contract.tenant.id if instance.contract and instance.contract.tenant else None
        if instance.contract and instance.contract.owner:
            representation['owner'] = instance.contract.owner.id if instance.contract and instance.contract.owner else None
        
        paid_status = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_paid_token').value)
        representation['paid_invoices'] = instance.invoices.filter(status=paid_status).count()
        representation['total_pending_invoices'] = sum(invoice.left_to_pay for invoice in instance.invoices.exclude(status=paid_status))
        representation['total_pending_payments'] = instance.payment_commitments.filter(status__token=pending_status_token).count()
        return representation
    
    
    def get_remittances(self, obj):
        remittances = PaymentRemittance.objects.filter(payments__in=obj.payments.all()).order_by('-created_at')
        rem_data = []
        for remittance in remittances:
            rem_data.append({
                'id': remittance.id,
                'token': remittance.token,
                'sent_at': remittance.sent_at,
                'sent_by': remittance.sent_by.username if remittance.sent_by else None,
            })
        return rem_data
    
    def get_joined_payments(self, obj):
        joined_payments = JoinedPayment.objects.filter(payments__in=obj.payments.all()).order_by('-created_at')
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
    
    def get_contract_piggy_bank(self, obj):
        if obj.contract and obj.contract.piggy_bank:
            return obj.contract.piggy_bank.amount
        return 0
    
    def get_usable_remaining(self, obj):
        payment_status_paid = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)
        payments_invoices = Payment.objects.filter(invoice__in=obj.invoices.all()).exclude(status=payment_status_paid)
        usable_remaining = False
        counter = 0
        while not usable_remaining and counter < len(payments_invoices):
            payment = payments_invoices[counter]
            if payment.amount <= obj.remaining_to_share and payment.amount > 0:
                usable_remaining = True
            counter += 1
            
        return usable_remaining
        
    def get_contract(self, obj):
        if not obj.contract:
            return {
                'id': None,
                'token': None,
                'holder': None,
                'contract_active': False
            }
        status_active_token = ConfigProject.objects.get(token='contract_active_token').value
        return {
            'id': obj.contract.id, 
            'token': obj.contract.token,
            'holder': PersonSerializer(read_only=True, required=False, allow_null=True).to_representation(obj.contract.holder) if obj.contract.holder else None,
            'tenant': PersonSerializer(read_only=True, required=False, allow_null=True).to_representation(obj.contract.tenant) if obj.contract.tenant else None,
            'owner': PersonSerializer(read_only=True, required=False, allow_null=True).to_representation(obj.contract.owner) if obj.contract.owner else None,
            'contract_active': obj.contract.status.token == status_active_token if obj.contract.status else False,
        }
    
    def get_invoices(self, obj):
        invoices = obj.invoices.all()
        data = []
        for invoice in invoices:
            data.append({
                'id': invoice.id,
                'token': invoice.token,
                'title_final': invoice.title_final,
                'total_final': invoice.total_final,
                'left_to_pay': invoice.left_to_pay,
                'serie_final': invoice.serie_final,
            })
        
        return data

    def get_incidents(self, obj):
        return obj.incidents.all().count()
    
class CommitmentDepositSaveSerializer(serializers.ModelSerializer):
    
    status_token = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = CommitmentDeposit
        fields = '__all__'
    
    
    def update(self, instance, validated_data):
        print("updating commitment deposit")
        request = self.context.get('request')
        user = request.user if request else None
        status_token = validated_data.pop('status_token', None)
        
        if status_token:
            status_cancel = CommitmentDepositStatus.objects.get(token=ConfigProject.objects.get(token='commitment_deposit_status_cancelled_token').value)
            
            status_instance = CommitmentDepositStatus.objects.get(token=status_token)
            
            logger_data = {
                'object': instance,
                'previous_status': instance.status,
                'current_status': status_instance,
                'user': user,
            }
            
            log = LogCommitmentDepositMovement.objects.create(**logger_data)
            
            if status_instance.token == status_cancel.token:
                payment_commitment_status_partially_paid = PaymentCommitmentStatus.objects.get(token=ConfigProject.objects.get(token='payment_commitment_status_partially_paid_token').value)
                payment_commitment_status_pending = PaymentCommitmentStatus.objects.get(token=ConfigProject.objects.get(token='payment_commitment_status_pending_token').value)
                payment_commitment_status_cancel = PaymentCommitmentStatus.objects.get(token=ConfigProject.objects.get(token='payment_commitment_status_cancelled_token').value)
                payment_expired_status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_expired_token').value)
                payment_pending_status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_pending_token').value)
                payment_cancelled_status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_cancelled_token').value)
                payment_paid_status_token = ConfigProject.objects.get(token='payment_status_paid_token').value
                invoice_confirmed_status = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_confirmed_token').value)
                invoice_paid_status = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_paid_token').value)
                
                # Include Confirmed status if it exists
                valid_filter_statuses = [payment_commitment_status_partially_paid, payment_commitment_status_pending]
                try:
                    confirmed_token = ConfigProject.objects.get(token='payment_commitment_status_confirmed_token').value
                    payment_commitment_status_confirmed = PaymentCommitmentStatus.objects.filter(token=confirmed_token).first()
                    if payment_commitment_status_confirmed:
                        valid_filter_statuses.append(payment_commitment_status_confirmed)
                except (ConfigProject.DoesNotExist, PaymentCommitmentStatus.DoesNotExist):
                    pass

                deposit_payments = PaymentCommitment.objects.filter(commitment_deposit=instance, status__in=valid_filter_statuses)
                deposit_payments.update(status=payment_commitment_status_cancel)
                
                invoices = instance.invoices.exclude(status=invoice_paid_status)
                invoice_payments = Payment.objects.filter(invoice__in=invoices).exclude(status__token=payment_paid_status_token).distinct()
                invoices.update(status=invoice_confirmed_status)
                today = datetime.datetime.now().date()
                for payment in invoice_payments:
                    if payment.due_date < today:
                        payment.status = payment_expired_status
                    else:
                        payment.status = payment_pending_status
                    payment.save()
                commitment_payments = Payment.objects.filter(
                    commitment_deposit=instance
                    ).exclude(status__token=payment_paid_status_token).distinct()
                for payment in commitment_payments:
                    payment.status = payment_cancelled_status
                    payment.save()
            
            instance.status = status_instance
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        return instance

class CommitmentDepositListSerializer(serializers.ModelSerializer):
    
    status_name = serializers.CharField(source='status.name')
    status_color = serializers.CharField(source='status.color')
    total_invoices = serializers.SerializerMethodField()
    contract = serializers.SerializerMethodField()
    
    class Meta:
        model = CommitmentDeposit
        fields = [
            'created_at', 'id', 'token', 
            'remaining', 'status_name', 'status_color',
            'total_invoices', 'due_date', 'contract',
            'total', 'customer_final', 'customer_token_final',
            'due_date', 'remaining_to_share'
        ]
    
    def get_total_invoices(self, obj):
        return obj.invoices.count()
    
    def get_contract(self, obj):
        if not obj.contract:
            return {
                'id': None, 
                'token': None,
                'holder_token': obj.customer_token_final,
                'holder_id': None,
                'holder': obj.customer_final,
            }
        return {
            'id': obj.contract.id, 
            'token': obj.contract.token,
            'holder_token': obj.contract.holder.token if obj.contract.holder else None,
            'holder_id': obj.contract.holder.id if obj.contract.holder else None,
            'holder': obj.contract.holder.name + ' ' + obj.contract.holder.surname if obj.contract.holder and obj.contract.holder.name and obj.contract.holder.surname else (obj.contract.holder.name if obj.contract.holder else None),
        }