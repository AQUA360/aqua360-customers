import uuid
from rest_framework import serializers

from billing.serializers.commitment_deposit_serializer import CommitmentDepositSerializer
from billing.serializers.value_objects_serializer import PaymentCommitmentStatusSerializer
from billing.utils.commitment_deposit_service import add_new_payment_deposit, add_wallet_payment
from contract.models import PiggyBankMovement
from coredata.models import ConfigProject
from coredata.utils.name_utils import generate_token

from ..models import *

class PaymentCommitmentSerializer(serializers.ModelSerializer):
    
    commitment_deposit = CommitmentDepositSerializer(read_only=True, required=False, allow_null=True)
    status = PaymentCommitmentStatusSerializer(read_only=True, required=False, allow_null=True)
    payment_type = serializers.SerializerMethodField()
    
    class Meta:
        model = PaymentCommitment
        fields = '__all__'
        
    def get_invoices(self, obj):
        invoices = obj.invoices.all()
        data = []
        for invoice in invoices:
            data.append({
                'id': invoice.id,
                'token': invoice.token,
                'number': invoice.number,
                'serie_final': invoice.serie_final,
                'left_to_pay': invoice.left_to_pay,
                'status_token': invoice.status.token,
                'status_name': invoice.status.name,
                'status_color': invoice.status.color,
                'title_final': invoice.title_final,
                'total_final': invoice.total_final,
            })
        
        return data
    
    def get_payment_type(self, obj):
        from contract.serializers.value_objects_serializer import PaymentTypeSerializer 
        return PaymentTypeSerializer(read_only=True, required=False, allow_null=True).to_representation(obj.payment_type)
        
    
class PaymentCommitmentSaveSerializer(serializers.ModelSerializer):
    
    status_token = serializers.CharField(required=False, allow_blank=True)
    commitment_deposit_id = serializers.IntegerField(required=False, allow_null=True)
    payment_type_id = serializers.IntegerField(required=False, allow_null=True)
    wallet_payment_date = serializers.DateField(required=False, allow_null=True)
    
    class Meta:
        model = PaymentCommitment
        fields = '__all__'
    
    def create(self, validated_data):
        print("creating payment commitment")
        
        commitment_deposit_id = validated_data.pop('commitment_deposit_id', None)
        payment_type_id = validated_data.pop('payment_type_id', None)
        is_guide = validated_data.get('is_guide', False)
        is_wallet = validated_data.pop('is_wallet', False)
        
        validated_data['token'] = generate_token(PaymentCommitment)
        
        commitment_deposit = None
        if commitment_deposit_id:
            commitment_deposit = CommitmentDeposit.objects.get(id=commitment_deposit_id)
            validated_data['commitment_deposit'] = commitment_deposit
            
            if not is_guide:
                payment_commitment_paid = PaymentCommitmentStatus.objects.get(token=ConfigProject.objects.get(token='payment_commitment_status_paid_token').value)
                validated_data['status'] = payment_commitment_paid
        
        if payment_type_id:
            payment_type_instance = PaymentType.objects.get(id=payment_type_id)
            validated_data['payment_type'] = payment_type_instance
            if payment_type_instance.token == "BALANCE":
                contract = commitment_deposit.contract if commitment_deposit else None
                if contract and contract.piggy_bank:
                    piggy_bank = contract.piggy_bank
                    piggy_bank.amount = float(piggy_bank.amount) - float(validated_data['currently_paid'])
                    if piggy_bank.amount < 0:
                        piggy_bank.amount = 0
                    piggy_bank.save()
                    PiggyBankMovement.objects.create(
                        token=generate_token(PiggyBankMovement),
                        piggy_bank=piggy_bank,
                        amount=validated_data['currently_paid'],
                        is_positive=False,
                        movement_date=validated_data['payment_date'],
                        commitment_deposit=commitment_deposit,
                    )
        try:
            company_bank_id = self.initial_data.get('company_iban') or self.initial_data.get('company_bank')
            company_bank = None
            if company_bank_id:
                from service.models import CompanyBank
                company_bank = CompanyBank.objects.filter(id=company_bank_id).first()
                if company_bank:
                    if company_bank.iban:
                        validated_data['payment_bank_final'] = company_bank.iban
                    if company_bank.swift:
                        validated_data['payment_swift_final'] = company_bank.swift
        except Exception as e:
            print(e)
            company_bank = None

        payment = super().create(validated_data)
        
        if not is_guide:
            request = self.context.get('request')
            user = request.user if request else None
            add_new_payment_deposit(payment, user, is_wallet, company_bank)
        
        return payment
    
    def update(self, instance, validated_data):
        from logger.models import LogCommitmentDepositMovement
        
        print("updating payment commitment")
        
        payment_type_id = validated_data.pop('payment_type_id', None)
        status_token = validated_data.pop('status_token', None)
        wallet_payment_date = validated_data.pop('wallet_payment_date', None)
        
        if status_token:
            status_instance = PaymentCommitmentStatus.objects.get(token=status_token)
            instance.status = status_instance
        
        if payment_type_id:
            payment_type_instance = PaymentType.objects.get(id=payment_type_id)
            validated_data['payment_type'] = payment_type_instance
            
            
        try:
            company_bank_id = self.initial_data.get('company_iban') or self.initial_data.get('company_bank')
            company_bank = None
            if company_bank_id:
                from service.models import CompanyBank
                company_bank = CompanyBank.objects.filter(id=company_bank_id).first()
                if company_bank:
                    if company_bank.iban:
                        validated_data['payment_bank_final'] = company_bank.iban
                    if company_bank.swift:
                        validated_data['payment_swift_final'] = company_bank.swift
        except Exception as e:
            print(e)
            company_bank = None

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if payment_type_id:
            request = self.context.get('request')
            user = request.user if request else None
            new_payment = add_wallet_payment(instance, user, False, wallet_payment_date, company_bank)
            logger_data = {
                'object': instance.commitment_deposit,
                'previous_status': instance.commitment_deposit.status,
                'current_status': instance.commitment_deposit.status,
                'previous_remaining': instance.commitment_deposit.remaining,
                'current_remaining': instance.commitment_deposit.remaining,
                'new_wallet': new_payment,
                'user': user,
            }
            log = LogCommitmentDepositMovement.objects.create(**logger_data)
        
        return instance
