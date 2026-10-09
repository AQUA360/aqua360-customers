from rest_framework import serializers

from billing.models import CommitmentDepositStatus, Invoice, Payment, PaymentStatus
from billing.serializers.estimated_bag_serializer import EstimatedBagSerializer
from contract.serializers.bail_serializer import BailMinimalSerializer
from contract.serializers.bonification_serializer import BonificationSerializer
from contract.serializers.contract_clause_serializer import ContractClauseSerializer
from contract.serializers.contract_price_rate_serializer import ContractPriceRateSerializer
from contract.serializers.contract_serializer import ContractObservationSerializer
from contract.serializers.contract_surrogation_serializer import ContractSurrogationSerializer
from contract.serializers.contract_tenant_change_serializer import ContractTenantChangeSerializer
from contract.serializers.contract_termination_request_serializer import ContractTerminationRequestMinimalSerializer
from contract.serializers.piggy_bank_serializer import PiggyBankSerializer
from contract.serializers.value_objects_serializer import ContractCategorySerializer, ContractClientTypeSerializer, ContractRequestDocumentationSerializer, ContractStatusSerializer, ContractUseTypeSerializer, ContractDebtManagementSerializer
from coredata.models import ConfigProject
from documentmanager.serializers import DocumentSerializer
from service.models import SupplyPoint
from contract.models import  Contract
from coredata.serializers import PersonContactSerializer, PersonSerializer, PersonAddressSerializer, PersonCNAESerializer
from billing.serializers.general_payment_serializer import GeneralPaymentSerializer
from contract.serializers.contract_data_change_serializer import ContractDataChangeSerializer
from contract.serializers.variable_serializer import VariableSerializer
from contract.serializers.contract_representative_serializer import ContractRepresentativeSerializer
from service.serializers.supply_point_serializer import SupplyPointSerializer
from auth.serializers import UserMinimalSerializer
from django.db.models import Sum

class PinnedContractMinimalSerializer(serializers.ModelSerializer):
    user_checked = UserMinimalSerializer(many=True, read_only=True, required=False, allow_null=True)
    class Meta:
        model = Contract
        fields = '__all__'
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        if instance.holder:
            representation['holder_is_juridic'] = instance.holder.is_juridic
            representation['holder_full'] = f"{instance.holder.name} {instance.holder.surname} ({instance.holder.token})"
            representation['holder_vulnerability_level'] = instance.holder.vulnerability_level
        else:
            representation['holder_is_juridic'] = False
            representation['holder_full'] = ''
            representation['holder_vulnerability_level'] = None
        representation['tenant_vulnerability_level'] = instance.tenant.vulnerability_level if instance.tenant else None
        representation['owner_vulnerability_level'] = instance.owner.vulnerability_level if instance.owner else None
        
        representation['communication_missing'] = False
        if instance.communication_type == 'DIGITAL':
            if not instance.person_contact_email and not instance.person_contact_sms.exists():
                representation['communication_missing'] = True
            if instance.person_contact_email and (instance.person_contact_email.email == '' or instance.person_contact_email.email is None):
                representation['communication_missing'] = True
        elif instance.communication_type == 'PAPER':
            if not instance.address_contact:
                representation['communication_missing'] = True
        
        representation['email_missing'] = False
        if instance.communication_type == 'DIGITAL':
            if instance.person_contact_email and (instance.person_contact_email.email == '' or instance.person_contact_email.email is None):
                representation['email_missing'] = True
            
        return representation


class PinnedContractSerializer(serializers.ModelSerializer):
    
    supply_point_default = SupplyPointSerializer(read_only=True, required=False, allow_null=True)
    supply_points = serializers.SerializerMethodField()
    status = ContractStatusSerializer(read_only=True, required=False, allow_null=True)
    
    use_type = ContractUseTypeSerializer(read_only=True, required=False, allow_null=True)
    client_type = ContractClientTypeSerializer(read_only=True, required=False, allow_null=True)
    category = ContractCategorySerializer(read_only=True, required=False, allow_null=True)
    contract_file = DocumentSerializer(read_only=True, required=False, allow_null=True)
    
    owner = PersonSerializer(read_only=True, required=False, allow_null=True)
    tenant = PersonSerializer(read_only=True, required=False, allow_null=True)
    holder = PersonSerializer(read_only=True, required=False, allow_null=True)
    representatives = ContractRepresentativeSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    address_billing = PersonAddressSerializer(read_only=True, required=False, allow_null=True)
    address_contact = PersonAddressSerializer(read_only=True, required=False, allow_null=True)
    payment = GeneralPaymentSerializer(read_only=True, required=False, allow_null=True)
    
    CNAE = PersonCNAESerializer(read_only=True, required=False, allow_null=True)
    variables = VariableSerializer(many=True, read_only=True, required=False, allow_null=True)
    debt_management = ContractDebtManagementSerializer(read_only=True, required=False, allow_null=True)
    data_changes = ContractDataChangeSerializer(many=True, read_only=True, required=False, allow_null=True)
    documentation_files = ContractRequestDocumentationSerializer(many=True, read_only=True, required=False, allow_null=True)
    clauses = ContractClauseSerializer(many=True, read_only=True, required=False, allow_null=True)
    surrogations = ContractSurrogationSerializer(many=True, read_only=True, required=False, allow_null=True)
    tenant_changes = ContractTenantChangeSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    person_contact_email = PersonContactSerializer(read_only=True, required=False, allow_null=True)
    person_contact_sms = PersonContactSerializer(many=True, read_only=True, required=False, allow_null=True)
    contacts = PersonContactSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    registration_price_rates = serializers.SerializerMethodField()
    price_rates = serializers.SerializerMethodField()
    show_price_rates = serializers.SerializerMethodField()
    bonifications = BonificationSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    user_checked = UserMinimalSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    bails = BailMinimalSerializer(many=True, read_only=True, required=False, allow_null=True)
    calendar_tasks = serializers.SerializerMethodField()
    piggy_bank = PiggyBankSerializer(read_only=True, required=False, allow_null=True)
    estimated_bags = EstimatedBagSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    general_invoice = serializers.SerializerMethodField()
    
    request_invoices = serializers.SerializerMethodField()
    vulnerability_requests = serializers.SerializerMethodField()
    active_vulnerability_requests = serializers.SerializerMethodField()
    active_commitment_deposits = serializers.SerializerMethodField()
    active_claim_requests = serializers.SerializerMethodField()
    active_contract_termination = serializers.SerializerMethodField()
    last_contract_termination = serializers.SerializerMethodField()
    supply_point_ids = serializers.SerializerMethodField()
    important_observations = serializers.SerializerMethodField()
    incidents = serializers.SerializerMethodField()
    debt_amount = serializers.SerializerMethodField()
    total_debt_payments = serializers.SerializerMethodField()
    
    class Meta:
        model = Contract
        fields = '__all__'
    
    def get_general_invoice(self, obj):
        if obj.general_invoice:
            return {
                'id': obj.general_invoice.id,
                'payment_type': obj.general_invoice.payment.type.name if obj.general_invoice.payment and obj.general_invoice.payment.type else None,
                'payment_iban': obj.general_invoice.payment.IBAN.iban if obj.general_invoice.payment and obj.general_invoice.payment.IBAN else None,
                'address_billing': str(obj.general_invoice.address_billing.address) if obj.general_invoice.address_billing else None,
                'address_contact': str(obj.general_invoice.address_contact.address) if obj.general_invoice.address_contact else None,
                'total_contracts': obj.general_invoice.contracts.count(),
            }
        return None
    
    def get_request_invoices(self, obj):
        request_invoices = []
        if obj.contract_request:
            try:
                type_final = ConfigProject.objects.get(token='invoice_type_invoice_token').value
                invoices = Invoice.objects.filter(
                    contract_request=obj.contract_request,
                    type__token=type_final
                    ).order_by('-created_at')
                for invoice in invoices:
                    request_invoices.append({
                        'id': invoice.id,
                        'token': invoice.token,
                        'serie_final': invoice.serie_final,
                        'title_final': invoice.title_final,
                        'total_final': invoice.total_final,
                        'status_name': invoice.status.name,
                        'status_color': invoice.status.color,
                        'type_token': invoice.type.token,
                        'left_to_pay': invoice.left_to_pay,
                        'total_final': invoice.total_final,
                        'customer_final': invoice.customer_final,
                        'customer_token_final': invoice.customer_token_final,
                        'due_date': invoice.due_date,
                        'type_final': invoice.type_final,
                    })
            except Exception as e:
                return []
        return request_invoices
    
    def get_price_rates(self, obj):
        price_rates = obj.price_rates.all().order_by('price_rate__product__position')
        return ContractPriceRateSerializer(price_rates, many=True, read_only=True).data
    
    def get_show_price_rates(self, obj):
        from pricing.serializers.price_rate_serializer import PriceRateSerializer
        contract_price_rates = obj.price_rates.all().order_by('price_rate__product__position')
        price_rates = [price_rate.price_rate for price_rate in contract_price_rates]
        price_rates = list(set(price_rates))
        return PriceRateSerializer(price_rates, many=True, read_only=True).data
    
    def get_incidents(self, obj):
        from notification.models import Incident
        contract_incidents = Incident.objects.filter(contract=obj)
        return contract_incidents.count()
    
    def get_calendar_tasks(self, obj):
        from notification.serializers.calendar_task_serializer import CalendarTaskSerializer
        
        return CalendarTaskSerializer(obj.calendar_tasks.all().order_by('-set_date'), many=True, read_only=True, context=self.context).data
    
    def get_registration_price_rates(self, obj):
        from pricing.serializers.price_rate_serializer import PriceRateSerializer
        registration_price_rates = obj.registration_price_rates.all()
        return PriceRateSerializer(registration_price_rates, many=True, read_only=True).data
    
    def get_debt_amount(self, obj):
        from contract.utils.contract_list_queryset import contract_debt_amounts_by_contract_id

        try:
            return contract_debt_amounts_by_contract_id([obj.pk]).get(obj.pk, 0)
        except Exception:
            return 0
    
    def get_total_debt_payments(self, obj):
        try:
            payment_status_expired = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_expired_token').value)
            payment_status_returned = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_returned_token').value)
            contract_payments = Payment.objects.filter(invoice__contract=obj, status__in=[payment_status_expired,payment_status_returned])
            return contract_payments.count()
        except Exception:
            return 0
    
    def get_important_observations(self, obj):
        observations = obj.observations.filter(is_important=True, is_active=True)
        return ContractObservationSerializer(observations, many=True, context=self.context).data
    
    def get_supply_point_ids(self, obj):
        supply_points = obj.supply_points.all()
        return [supply_point.id for supply_point in supply_points]
    
    def get_supply_points(self, obj):
        request = self.context.get('request')
        return SupplyPointSerializer(obj.supply_points.all(), many=True, context={'request': request}).data
    
    def get_active_contract_termination(self, obj):
        from contract.models import ContractTerminationRequest
        contract_termination_cancelled_token = ConfigProject.objects.get(token='contract_termination_cancelled_token').value
        contract_termination_finished_token = ConfigProject.objects.get(token='contract_termination_completed_token').value
        contract_terminations = ContractTerminationRequest.objects.filter(contract=obj).exclude(status__token__in=[contract_termination_cancelled_token, contract_termination_finished_token])
        return contract_terminations.count() > 0

    def get_last_contract_termination(self, obj):
        from contract.models import ContractTerminationRequest
        contract_termination_cancelled_token = ConfigProject.objects.get(token='contract_termination_cancelled_token').value
        contract_terminations = ContractTerminationRequest.objects.filter(contract=obj).exclude(status__token=contract_termination_cancelled_token).order_by('-created_at')
        return ContractTerminationRequestMinimalSerializer(contract_terminations.first(), context=self.context).data if contract_terminations.exists() else None
    
    def get_active_vulnerability_requests(self, obj):
        vulnerability_pending_token = ConfigProject.objects.get(token='vulnerability_request_status_pending_token').value
        vulnerability_requests = obj.vulnerability_requests.filter(status__token=vulnerability_pending_token)
        return vulnerability_requests.count() > 0
    
    def get_vulnerability_requests(self, obj):
        vulnerability_requests = obj.vulnerability_requests.all()
        request_data = []
        for request in vulnerability_requests:
            request_data.append({
                'id': request.id,
                'token': request.token,
                'status_name': request.status.name,
                'status_color': request.status.color,
                'person_name': request.person.name,
                'person_surname': request.person.surname,
                'person_token': request.person.token,
            })
        return request_data

    def get_active_commitment_deposits(self, obj):
        try:
            deposit_paid_token = ConfigProject.objects.get(token='commitment_deposit_status_paid_token').value
            deposit_cancelled_token = ConfigProject.objects.get(token='commitment_deposit_status_cancelled_token').value
            commitment_deposits = obj.commitment_deposits.exclude(status__token__in=[deposit_paid_token, deposit_cancelled_token])
            return commitment_deposits.count()
        except Exception:
            return 0

    def get_active_claim_requests(self, obj):
        from claimrequest.models import ClaimRequestStatus, ClaimRequest
        
        pending_claim = ConfigProject.objects.get(token='claim_request_status_pending_token').value
        accepted_claim = ConfigProject.objects.get(token='claim_request_status_accepted_token').value
        claim_requests = ClaimRequest.objects.filter(payments__contract=obj, status__token__in=[pending_claim, accepted_claim])
        return claim_requests.count() > 0

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        if instance.holder:
            representation['holder_full'] = f"{instance.holder.name} {instance.holder.surname} ({instance.holder.token})"
            representation['holder_vulnerability_level'] = instance.holder.vulnerability_level
        else:
            representation['holder_full'] = ''
            representation['holder_vulnerability_level'] = None
        representation['tenant_vulnerability_level'] = instance.tenant.vulnerability_level if instance.tenant else None
        representation['owner_vulnerability_level'] = instance.owner.vulnerability_level if instance.owner else None
        
        representation['communication_missing'] = False
        if instance.communication_type == 'DIGITAL':
            if not instance.person_contact_email and not instance.person_contact_sms.exists():
                representation['communication_missing'] = True
            if instance.person_contact_email and (instance.person_contact_email.email == '' or instance.person_contact_email.email is None):
                representation['communication_missing'] = True
        elif instance.communication_type == 'PAPER':
            if not instance.address_contact:
                representation['communication_missing'] = True
        
        representation['email_missing'] = False
        if instance.communication_type == 'DIGITAL':
            if instance.person_contact_email and (instance.person_contact_email.email == '' or instance.person_contact_email.email is None):
                representation['email_missing'] = True
            
        representation['total_persons'] = instance.total_persons
        representation['total_persons_text'] = f"{instance.total_persons} persones" if instance.total_persons > 1 else f"{instance.total_persons} persona"
        
        #supply_point = SupplyPoint.objects.filter(token = instance.supply_point.token).first()
        try:
            supply_point = SupplyPoint.objects.filter(id = instance.supply_point_default_id).first()
            if supply_point:
                representation['supply_point'] = str(supply_point.address)
        except:
            print("supply_point not loaded")
        
        return representation