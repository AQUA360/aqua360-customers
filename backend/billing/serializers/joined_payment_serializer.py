from rest_framework import serializers
from django_filters import rest_framework as filters

from auth.serializers import UserMinimalSerializer
from billing.utils.joined_payment_service import generate_joined_payment_id, mark_payments_as_paid, register_joined_payment_log
from claimrequest.serializers.claim_request_list_serializer import ClaimRequestListSerializer
from contract.models import Contract, PaymentType
from contract.serializers.contract_serializer import ContractMinimalSerializer
from coredata.models import ConfigProject, Person
from coredata.serializers import PersonMinimalSerializer
from billing.serializers.payment_serializer import PaymentListSerializer
from billing.serializers.value_objects_serializer import JoinedPaymentStatusSerializer
from ..models import ( JoinedPayment, JoinedPaymentObservation, JoinedPaymentStatus, Payment )
from django.utils.translation import gettext as _

class JoinedPaymentObservationSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)
    
    class Meta:
        model = JoinedPaymentObservation
        fields = '__all__'

class JoinedPaymentSerializer(serializers.ModelSerializer):
    status = JoinedPaymentStatusSerializer(read_only=True, required=False, allow_null=True)
    person = PersonMinimalSerializer(read_only=True, required=False, allow_null=True)
    contract = ContractMinimalSerializer(read_only=True, required=False, allow_null=True)
    payments = PaymentListSerializer(many=True, read_only=True, required=False, allow_null=True)
    claim_request = ClaimRequestListSerializer(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = JoinedPayment
        fields = '__all__'
    
    def get_supply_point(self, obj):
        from service.serializers.supply_point_serializer import SupplyPointMinimalSerializer
        return SupplyPointMinimalSerializer(obj.supply_point).data

class JoinedPaymentSaveSerializer(serializers.ModelSerializer):
    
    contract_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    person_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    payments_data = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    payment_method_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    due_date = serializers.DateField(write_only=True, required=False, allow_null=True)
    payment_date = serializers.DateField(write_only=True, required=False, allow_null=True)
    status_token = serializers.CharField(write_only=True, required=False, allow_null=True)
    
    
    class Meta:
        model = JoinedPayment
        fields = '__all__'
        
    def create(self, validated_data):
        contract_id = validated_data.pop('contract_id', None)
        person_id = validated_data.pop('person_id', None)
        payments_data = validated_data.pop('payments_data', None)
        payment_method_id = validated_data.pop('payment_method_id', None)
        
        person_ins = None
        
        if contract_id:
            contract = Contract.objects.get(id=contract_id)
            person_ins = contract.holder
            validated_data['contract'] = contract
            validated_data['person'] = contract.holder
        if person_id:
            person = Person.objects.get(id=person_id)
            person_ins = person
            validated_data['person'] = person
        
        if person_ins:
            validated_data['customer_final'] = f"{person_ins.name} {person_ins.surname if person_ins.surname else ''}"
            validated_data['customer_token_final'] = person_ins.token
        
        if payment_method_id:
            payment_method = PaymentType.objects.get(id=payment_method_id)
            validated_data['payment_type'] = payment_method
            validated_data['payment_type_name'] = payment_method.name
            validated_data['payment_type_token'] = payment_method.token
        
        if payments_data:
            payments = Payment.objects.filter(id__in=payments_data)
            validated_data['payments'] = payments
            validated_data['total_final'] = sum(payment.amount for payment in payments)
        
        validated_data['status'] = JoinedPaymentStatus.objects.get(is_default=True)
        number = generate_joined_payment_id('05')
        validated_data['token'] = number
        validated_data['number'] = number
        object = super().create(validated_data)
        
        register_joined_payment_log(object, None, object.status, _("Joined payment created"), self.context['request'].user)
        
        return object
    
    def update(self, instance, validated_data):
        status_paid_token = ConfigProject.objects.get(token="joined_payment_status_paid_token").value
        status_cancel_token = ConfigProject.objects.get(token="joined_payment_status_cancelled_token").value
        status_token = validated_data.pop('status_token', None)
        payment_method_id = validated_data.pop('payment_method_id', None)
        user = self.context['request'].user
        
        if payment_method_id:
            payment_method = PaymentType.objects.get(id=payment_method_id)
            validated_data['payment_type'] = payment_method
            validated_data['payment_type_name'] = payment_method.name
            validated_data['payment_type_token'] = payment_method.token
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if status_token:
            new_status = JoinedPaymentStatus.objects.get(token=status_token)
            
            register_joined_payment_log(instance, instance.status, new_status, None, user)
            instance.status = new_status
            if new_status.token == status_paid_token:
                mark_payments_as_paid(instance, user)
        
        instance.save()
        
        return super().update(instance, validated_data)

class JoinedPaymentListSerializer(serializers.ModelSerializer):
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    
    class Meta:
        model = JoinedPayment
        fields = [
            'id', 'token', 'customer_final', 'customer_token_final', 
            'status_name', 'status_color', 'total_final',
            'due_date', 'created_at', 'payment_date', 'payment_type_name'
            ]
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        return representation

