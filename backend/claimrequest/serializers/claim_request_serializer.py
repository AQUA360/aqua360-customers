from rest_framework import serializers

from auth.serializers import UserMinimalSerializer
from claimrequest.serializers.claim_request_status_serializer import ClaimRequestStatusSerializer
from coredata.models import ConfigProject
from order.serializers.order_serializer import OrderMinimalSerializer
from ..models import ClaimRequest
from billing.serializers.invoice_serializer import InvoiceMinimalSerializer
from .claim_request_step_serializer import ClaimRequestStepSerializer
from contract.serializers.contract_termination_request_serializer import ContractTerminationRequestMinimalSerializer

class ClaimRequestSerializer(serializers.ModelSerializer):
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    current_step = ClaimRequestStepSerializer(read_only=True)
    current_step_name = serializers.CharField(source='current_step.name', read_only=True)
    current_step_position = serializers.IntegerField(source='current_step.position', read_only=True)
    current_step_is_completed = serializers.BooleanField(source='current_step.is_completed', read_only=True)
    current_step_due_date = serializers.DateField(source='current_step.due_date', read_only=True)
    total_payments = serializers.SerializerMethodField()
    total_contracts = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    pending_payments_count = serializers.SerializerMethodField()
    excluded_payments_count = serializers.SerializerMethodField()
    vulnerable_payments_count = serializers.SerializerMethodField()
    paid_payments_count = serializers.SerializerMethodField()
    contract_termination_requests = ContractTerminationRequestMinimalSerializer(many=True, read_only=True)
    cut_suply_orders = serializers.SerializerMethodField()
    remove_meter_orders = serializers.SerializerMethodField()
    vulnerable_requests_count = serializers.SerializerMethodField()
    vulnerable_pending_requests_count = serializers.SerializerMethodField()
    vulnerable_accepted_requests_count = serializers.SerializerMethodField()
    vulnerable_accepted_requests_not_exclosed_count = serializers.SerializerMethodField()
    status = ClaimRequestStatusSerializer(read_only=True, required=False, allow_null=True)
    user = UserMinimalSerializer(required=False, allow_null=True)
    
    class Meta:
        model = ClaimRequest
        fields = [
            'id', 'token', 'created_at', 'updated_at', 'status', 'status_name', 'status_color',
            'template', 'template_name',
            'current_step', 'current_step_name', 'current_step_position',
            'current_step_is_completed', 'current_step_due_date',
            'due_date', 'description', 'total_payments', 'total_contracts', 'amount',
            'pending_payments_count', 'excluded_payments_count', 'vulnerable_payments_count', 'paid_payments_count',
            'contract_termination_requests', 'vulnerable_pending_requests_count', 'vulnerable_accepted_requests_count',
            'vulnerable_requests_count', 'vulnerable_accepted_requests_not_exclosed_count',
            'cut_suply_orders', 'remove_meter_orders', 'status', 'user'
        ]
    
    def get_remove_meter_orders(self, obj):
        orders = obj.orders.filter(type__token=ConfigProject.objects.get(token='order_type_remove_meter_token').value)
        order_data = []
        for order in orders:
            order_data.append({
                'id': order.id,
                'token': order.token,
                'contract_token': order.contract.token,
            })
        return order_data
    
    def get_cut_suply_orders(self, obj):
        orders = obj.orders.filter(type__token=ConfigProject.objects.get(token='order_type_supply_cut_token').value)
        order_data = []
        for order in orders:
            order_data.append({
                'id': order.id,
                'token': order.token,
                'contract_token': order.contract.token,
            })
        return order_data
    
    def get_vulnerable_accepted_requests_not_exclosed_count(self, obj):
        from ..models import ClaimRequestPayment
        from django.db.models import Q

        # Get the accepted token value only once
        accepted_token = ConfigProject.objects.only('value').get(token='vulnerability_request_status_accepted_token').value

        # Retrieve all accepted vulnerability request contract IDs directly
        accepted_contract_ids = obj.vulnerability_requests.filter(
            status__token=accepted_token
        ).values_list('contract_id', flat=True).distinct()

        # Count not-excluded payments directly
        return ClaimRequestPayment.objects.filter(
            claim_request=obj,
            contract_id__in=accepted_contract_ids,
            is_excluded=False
        ).count()

        
    
    def get_vulnerable_requests_count(self, obj):
        return obj.vulnerability_requests.all().count()
    
    def get_vulnerable_pending_requests_count(self, obj):
        requests = obj.vulnerability_requests.all()
        status_request_pending_token = ConfigProject.objects.get(token='vulnerability_request_status_pending_token').value
        return requests.filter(status__token=status_request_pending_token).count()
    
    def get_vulnerable_accepted_requests_count(self, obj):
        requests = obj.vulnerability_requests.all()
        status_request_accepted_token = ConfigProject.objects.get(token='vulnerability_request_status_accepted_token').value
        return requests.filter(status__token=status_request_accepted_token).count()
    
    def get_total_payments(self, obj):
        return obj.total_payments or 0
    
    def get_total_contracts(self, obj):
        return obj.total_contracts or 0
    
    def get_amount(self, obj):
        return obj.amount or 0
    
    def get_pending_payments_count(self, obj):
        return obj.payments.filter(is_paid=False, is_excluded=False, is_vulnerable=False).count()
    
    def get_excluded_payments_count(self, obj):
        return obj.payments.filter(is_excluded=True).count()
    
    def get_vulnerable_payments_count(self, obj):
        return obj.payments.filter(is_vulnerable=True).count()

    def get_paid_payments_count(self, obj):
        return obj.payments.filter(is_paid=True).count()
        
    def to_representation(self, instance):
        representation = super().to_representation(instance)

        # Obtenim les factures dels pagaments
        payments = instance.payments.all()
        invoices = set()

        for claim_payment in payments:
            if claim_payment.payment and claim_payment.payment.invoice:
                invoices.add(claim_payment.payment.invoice)
        
        # representation['invoices'] = InvoiceMinimalSerializer(sorted(invoices, key=lambda inv: inv.customer_token_final), many=True).data
        representation['invoices'] = []

        return representation 