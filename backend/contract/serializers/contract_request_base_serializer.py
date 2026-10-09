from rest_framework import serializers

from contract.serializers.contract_price_rate_serializer import ContractPriceRateSerializer
from contract.serializers.contract_request_type_serializer import ContractRequestTypeListSerializer
from coredata.models import ConfigProject
from ..models import ContractRequest
from coredata.serializers import PersonSerializer
from service.serializers.supply_point_serializer import SupplyPointContractsSerializer
from .value_objects_serializer import ContractRequestTypeSerializer, ContractRequestStatusSerializer
from documentmanager.serializers import DocumentSerializer
from .variable_serializer import VariableSerializer
from .contract_clause_serializer import ContractClauseSerializer
from .contract_request_representative_serializer import ContractRequestRepresentativeSerializer
from billing.serializers.general_payment_serializer import GeneralPaymentSerializer
from .value_objects_serializer import ContractDebtManagementSerializer
from coredata.serializers import PersonAddressSerializer, PersonContactSerializer
from .value_objects_serializer import ContractRequestDocumentationSerializer
from .value_objects_serializer import ContractCategorySerializer, ContractUseTypeSerializer, ContractClientTypeSerializer
from .bonification_serializer import BonificationSerializer
from order.serializers.value_objects_serializer import OrderTypeSerializer
from order.serializers.order_serializer import OrderSerializer
from .value_objects_serializer import BailTypeSerializer
from coredata.serializers import PersonCNAESerializer

class ContractRequestSerializer(serializers.ModelSerializer):
    # person = PersonSerializer(read_only=True, required=False, allow_null=True)
    person_id = serializers.IntegerField(read_only=True, source='person.id')
    supply_point_default = SupplyPointContractsSerializer(read_only=True, required=False, allow_null=True)
    supply_points = SupplyPointContractsSerializer(many=True, read_only=True, required=False, allow_null=True)
    type = ContractRequestTypeListSerializer(read_only=True, required=False, allow_null=True)
    status = ContractRequestStatusSerializer(read_only=True, required=False, allow_null=True)

    contract_file = DocumentSerializer(read_only=True, required=False, allow_null=True)
    variables = VariableSerializer(many=True,read_only=True, required=False, allow_null=True)
    clauses = ContractClauseSerializer(many=True, read_only=True, required=False, allow_null=True)
    contract_delete = serializers.BooleanField(write_only=True, required=False, allow_null=True)

    # persons
    # owner = PersonSerializer(read_only=True, required=False, allow_null=True)
    # tenant = PersonSerializer(read_only=True, required=False, allow_null=True)
    # holder = PersonSerializer(read_only=True, required=False, allow_null=True)
    representatives = ContractRequestRepresentativeSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    address_billing = PersonAddressSerializer(read_only=True, required=False, allow_null=True)
    address_contact = PersonAddressSerializer(read_only=True, required=False, allow_null=True)
    payment = GeneralPaymentSerializer(read_only=True, required=False, allow_null=True)
    debt_management = ContractDebtManagementSerializer(read_only=True, required=False, allow_null=True)
    
    person_contact_email = PersonContactSerializer(read_only=True, required=False, allow_null=True)
    person_contact_sms = PersonContactSerializer(many=True, read_only=True, required=False, allow_null=True)
    contacts = PersonContactSerializer(many=True, read_only=True, required=False, allow_null=True)

    documentation_files = ContractRequestDocumentationSerializer(many=True, read_only=True, required=False, allow_null=True)
    price_rates = ContractPriceRateSerializer(many=True, read_only=True, required=False, allow_null=True)
    registration_price_rates = serializers.SerializerMethodField()
    category = ContractCategorySerializer(read_only=True, required=False, allow_null=True)
    use_type = ContractUseTypeSerializer(read_only=True, required=False, allow_null=True)
    client_type = ContractClientTypeSerializer(read_only=True, required=False, allow_null=True)
    bonifications = BonificationSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    order_types = OrderTypeSerializer(many=True, read_only=True, required=False, allow_null=True)
    orders = OrderSerializer(many=True, read_only=True, required=False, allow_null=True)
    pending_orders = serializers.SerializerMethodField()
    bail_types = BailTypeSerializer(many=True,read_only=True, required=False, allow_null=True)
    
    cnaes = PersonCNAESerializer(many=True,read_only=True, required=False, allow_null=True)
    invoices = serializers.SerializerMethodField()
    
    can_change = serializers.SerializerMethodField()
    
    class Meta:
        model = ContractRequest
        fields = '__all__'

    def get_pending_orders(self, obj):
        completed_status_token = ConfigProject.objects.get(token='order_status_completed_token').value
        cancelled_status_token = ConfigProject.objects.get(token='order_status_cancelled_token').value
        return obj.orders.exclude(status__token__in=[completed_status_token, cancelled_status_token]).values_list('id', flat=True)
    
    def get_can_change(self, obj):
        return self.context.get('user_can_change_contractrequest', False)

    def get_invoices(self, obj):
        from billing.models import Invoice
        invoice_data = []
        invoices = Invoice.objects.filter(contract_request=obj)
        invoice_type_token = ConfigProject.objects.get(token='invoice_type_invoice_token').value
        for invoice in invoices:
            has_invoice = Invoice.objects.filter(budget_token=invoice.token, type__token=invoice_type_token).order_by('-created_at').first()
            invoice_data.append({
                'id': invoice.id,
                'token': invoice.token,
                'serie_final': invoice.serie_final,
                'title_final': invoice.title_final,
                'total_final': invoice.total_final,
                'status_name': invoice.status.name,
                'status_id': invoice.status.id,
                'status_token': invoice.status.token,
                'status_color': invoice.status.color,
                'type_token': invoice.type.token,
                'invoice_file_template': invoice.invoice_file_template is not None,
                'invoice_file': invoice.invoice_file.id if invoice.invoice_file else None,
                'budget_token': invoice.budget_token,
                'has_invoice': has_invoice is not None,
                'refactored_token': invoice.refactored_token,
                'entity': 'contract_termination_request' if invoice.contract_termination else 'contract_request',
                'object_id': invoice.contract_termination.id if invoice.contract_termination else obj.id,
                'type_token': invoice.type.token
            })
        return invoice_data
    
    def get_registration_price_rates(self, obj):
        from pricing.serializers.price_rate_serializer import PriceRateSerializer
        registration_price_rates = obj.registration_price_rates.all()
        return PriceRateSerializer(registration_price_rates, many=True, read_only=True).data
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        from .contract_termination_request_serializer import ContractTerminationRequestMinimalSerializer
        if instance.contract_termination_requests.all():
            representation['contract_termination_requests'] = ContractTerminationRequestMinimalSerializer(instance.contract_termination_requests.all(), many=True, context=self.context).data
        print("person", instance.person)
        representation['person_full_name'] = f"{instance.person.name} {instance.person.surname}" if instance.person else None
        if instance.owner:
            representation['owner_full_name'] = f"{instance.owner.name} {instance.owner.surname}" if instance.owner else None
        if instance.tenant:
            representation['tenant_full_name'] = f"{instance.tenant.name} {instance.tenant.surname}" if instance.tenant else None
        if instance.holder:
            representation['holder_full_name'] = f"{instance.holder.name} {instance.holder.surname}"
        
        representation['contract'] = None
        if instance.contract and instance.contract.first():
            representation['contract'] = {
                'id': instance.contract.first().id,
                'token': instance.contract.first().token,
                'holder': instance.contract.first().holder.id if instance.contract.first().holder else None,
            }
        
        return representation 