import datetime
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from auth.serializers import UserMinimalSerializer
from billing.serializers.estimated_bag_serializer import EstimatedBagSerializer
from billing.serializers.general_payment_serializer import GeneralPaymentSerializer
from billing.utils.payment_service import generate_mandate_id
from contract.serializers.bail_serializer import BailSerializer, BailMinimalSerializer
from contract.serializers.bonification_serializer import BonificationSerializer
from contract.serializers.contract_data_change_serializer import ContractDataChangeSerializer
from contract.serializers.contract_price_rate_serializer import ContractPriceRateSerializer
from contract.serializers.contract_request_type_serializer import ContractRequestTypeSerializer
from contract.serializers.contract_tenant_change_serializer import ContractTenantChangeSerializer
from contract.serializers.contract_minimal_serializer import ContractMinimalSerializer
from contract.serializers.piggy_bank_serializer import PiggyBankSerializer
from coredata.models import Person, PersonAddress, PersonContact, ConfigProject
from documentmanager.serializers import DocumentSerializer
from contract.management.commands.fill_contract_use_aca import fill_contract_use_aca
from notification.models import CalendarTask
from pricing.models import PriceRate
from service.models import Company, SupplyPoint
from contract.models import ( Contract, ContractCategory, ContractClientType, ContractDebtManagement, ContractDebtView, ContractLog, ContractObservation, ContractPriceRate, ContractRepresentative, ContractRequestType, ContractUseType )
from service.serializers.company_serializer import CompanyMinimalSerializer
from service.serializers.exploitation_serializer import ExploitationMinimalSerializer
from service.serializers.supply_point_serializer import SupplyPointMinimalSerializer
from coredata.serializers import PersonAddressSerializer, PersonContactSerializer, PersonSerializer, PersonCNAESerializer, PersonContractMinimalSerializer, PersonMinimalContractSerializer
from contract.serializers.value_objects_serializer import ContractDebtManagementSerializer, ContractRequestDocumentationSerializer, ContractStatusSerializer, ContractUseTypeSerializer, ContractClientTypeSerializer, ContractCategorySerializer, ContractRequestStatusSerializer
from .variable_serializer import VariableSerializer
from .contract_representative_serializer import ContractRepresentativeSaveSerializer, ContractRepresentativeSerializer
from .contract_request_serializer import ContractRequestSerializer, ContractRequestMinimalSerializer
from .contract_surrogation_serializer import ContractSurrogationSerializer
from .contract_clause_serializer import ContractClauseSerializer
from .contract_payment_serializer import ContractPaymentSerializer

from django.db.models import Q, Sum
from billing.models import CommitmentDepositStatus, GeneralPaymentMandateLog, Invoice, InvoiceStatus, Payment, PaymentStatus
from logger.models import LogContractTotalMembers
from contract.utils.contract_service import log_contract_phones_change
from contract.utils.contract_list_queryset import contract_debt_amounts_by_contract_id

class ContractObservationSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = ContractObservation
        fields = '__all__'
        
class ContractLogSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(read_only=True)
    source = serializers.SerializerMethodField()

    def get_source(self, obj):
        return 'log'

    class Meta:
        model = ContractLog
        fields = [
            'id',
            'created_at',
            'field_name',
            'old_value',
            'new_value',
            'operation_token',
            'user',
            'source',
        ]

def person_full_name(person):
    """Nom visible d'una persona per als logs i observacions del contracte."""
    if not person:
        return str(_("Cap"))
    return f"{person.name or ''} {person.surname or ''}".strip()


class ContractSerializer(serializers.ModelSerializer):
    supply_point_default = SupplyPointMinimalSerializer(read_only=True, required=False, allow_null=True)
    supply_points = serializers.SerializerMethodField()
    status = ContractStatusSerializer(read_only=True, required=False, allow_null=True)

    use_type = ContractUseTypeSerializer(read_only=True, required=False, allow_null=True)
    client_type = ContractClientTypeSerializer(read_only=True, required=False, allow_null=True)
    category = ContractCategorySerializer(read_only=True, required=False, allow_null=True)
    contract_file = DocumentSerializer(read_only=True, required=False, allow_null=True)
    # persons
    owner = PersonContractMinimalSerializer(read_only=True, required=False, allow_null=True)
    tenant = PersonContractMinimalSerializer(read_only=True, required=False, allow_null=True)
    holder = PersonContractMinimalSerializer(read_only=True, required=False, allow_null=True)
    representatives = ContractRepresentativeSerializer(many=True, read_only=True, required=False, allow_null=True)
    representatives_save = ContractRepresentativeSaveSerializer(many=True, write_only=True, required=False, allow_null=True)

    address_billing = PersonAddressSerializer(read_only=True, required=False, allow_null=True)
    address_contact = PersonAddressSerializer(read_only=True, required=False, allow_null=True)
    payment = GeneralPaymentSerializer(read_only=True, required=False, allow_null=True)
    
    CNAE = PersonCNAESerializer(read_only=True, required=False, allow_null=True)
    variables = VariableSerializer(many=True, read_only=True, required=False, allow_null=True)
    debt_management = ContractDebtManagementSerializer(read_only=True, required=False, allow_null=True)
    data_changes = ContractDataChangeSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    contract_request = ContractRequestMinimalSerializer(read_only=True, required=False, allow_null=True)
    contract_request_type = ContractRequestTypeSerializer(read_only=True, required=False, allow_null=True)
    
    documentation_files = ContractRequestDocumentationSerializer(many=True, read_only=True, required=False, allow_null=True)
    clauses = ContractClauseSerializer(many=True, read_only=True, required=False, allow_null=True)
    surrogations = ContractSurrogationSerializer(many=True, read_only=True, required=False, allow_null=True)
    tenant_changes = ContractTenantChangeSerializer(many=True, read_only=True, required=False, allow_null=True)

    person_contact_email = PersonContactSerializer(read_only=True, required=False, allow_null=True)
    person_contact_sms = PersonContactSerializer(many=True, read_only=True, required=False, allow_null=True)
    contacts = PersonContactSerializer(many=True, read_only=True, required=False, allow_null=True)

    #registration_price_rates = ContractPriceRateSerializer(many=True, read_only=True, required=False, allow_null=True)
    registration_price_rates = serializers.SerializerMethodField()
    price_rates = serializers.SerializerMethodField()
    show_price_rates = serializers.SerializerMethodField()
    tarifa_bop = serializers.SerializerMethodField()
    category = ContractCategorySerializer(read_only=True, required=False, allow_null=True)
    bonifications = BonificationSerializer(many=True, read_only=True, required=False, allow_null=True)
    company = CompanyMinimalSerializer(read_only=True, required=False, allow_null=True)
    
    bails = BailMinimalSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    vulnerability_requests = serializers.SerializerMethodField()
    active_vulnerability_requests = serializers.SerializerMethodField()
    active_commitment_deposits = serializers.SerializerMethodField()
    active_claim_requests = serializers.SerializerMethodField()
    active_contract_termination = serializers.SerializerMethodField()
    supply_point_ids = serializers.SerializerMethodField()
    piggy_bank = PiggyBankSerializer(read_only=True, required=False, allow_null=True)
    estimated_bags = EstimatedBagSerializer(many=True, read_only=True, required=False, allow_null=True)

    important_observations = serializers.SerializerMethodField()
    person_important_observations = serializers.SerializerMethodField()
    user_pinned = UserMinimalSerializer(read_only=True, required=False, allow_null=True)
    user_checked = UserMinimalSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    address_billing_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    address_contact_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    person_contact_email_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    phone_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    sms_phone_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    contract_use_type = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    contract_client_type = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    price_rates_ids = serializers.ListField(write_only=True, required=False, allow_null=True)
    registration_price_rates_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    category_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    company_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    total_persons = serializers.IntegerField(required=False, allow_null=True)
    debt_management_id = serializers.CharField(write_only=True, required=False, allow_null=True)
    payment_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    # Reassignacio directa de persones (sense subrogacio): la subrogacio formal
    # (ContractSurrogation) mou pagament, adreces i contactes; aquests camps nomes
    # canvien la persona del rol i en deixen traca.
    holder_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    owner_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    exploitation = serializers.SerializerMethodField()
    
    request_invoices = serializers.SerializerMethodField()
    incidents = serializers.SerializerMethodField()
    debt_amount = serializers.SerializerMethodField()
    total_debt_payments = serializers.SerializerMethodField()
    total_in_commitment_deposits = serializers.SerializerMethodField()
    calendar_tasks = serializers.SerializerMethodField()
    invoices = serializers.SerializerMethodField()
    billing_period_days = serializers.SerializerMethodField()
    
    observations_count = serializers.SerializerMethodField()
    call_register_count = serializers.SerializerMethodField()
    communications_count = serializers.SerializerMethodField()
    invoices_count = serializers.SerializerMethodField()
    general_invoices_count = serializers.SerializerMethodField()
    members_change_count = serializers.SerializerMethodField()
    orders_count = serializers.SerializerMethodField()
    pending_billing = serializers.SerializerMethodField()
    
    mandate_id = serializers.CharField(required=False, allow_null=True)
    mandate_id_overwrite = serializers.BooleanField(required=False, allow_null=True)
    registration_date = serializers.DateField(required=False, allow_null=True)

    is_pinned = serializers.BooleanField(write_only=True, required=False, allow_null=True)
    is_checked = serializers.BooleanField(write_only=True, required=False, allow_null=True)
    new_task = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    use_type_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    contract_request_type_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    is_fire = serializers.BooleanField(read_only=True)

    class Meta:
        model = Contract
        fields = '__all__'
    
    def get_exploitation(self, obj):
        if obj.contract_request_type and obj.contract_request_type.exploitation:
            return ExploitationMinimalSerializer(obj.contract_request_type.exploitation).data
        return ExploitationMinimalSerializer(obj.supply_point_default.connection.exploitation).data
    
    def get_billing_period_days(self, obj):
        try:
            period_type = ['mensual','bimestral','trimestral','semestral','anual']
            period_jumps = [1,2,3,6,12]
            biller_period = obj.supply_point_default.property.route_position.route.biller.period_type
            return period_jumps[period_type.index(biller_period)] * 30
        except:
            return None
    
    def get_pending_billing(self, obj):
        from billing.models import Reading
        config_status_tokens = [
            "billing_batch_processing_documents",
            "billing_batch_pending",
            "billing_batch_processing"
        ]
        billing_status_pending_token = ConfigProject.objects.filter(token__in=config_status_tokens).values_list('value', flat=True)
        
        readings = Reading.objects.filter(
            contract=obj,
            is_active=True,
            is_control=False,
            billing__status__token__in=billing_status_pending_token
        )
        return readings.count() > 0
    
    def get_request_invoices(self, obj):
        request_invoices = []
        try:
            type_final = ConfigProject.objects.get(token='invoice_type_invoice_token').value
            invoices = Invoice.objects.filter(
                contract_request__token=obj.token,
                type_final=type_final
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
    
    def get_important_observations(self, obj):
        observations = obj.observations.filter(is_important=True, is_active=True)
        return ContractObservationSerializer(observations, many=True, context=self.context).data

    def get_debt_amount(self, obj):
        # Llegeix vw_contract_debt (statistics/migrations/0033_create_vw_contract_debt.py):
        # tots els pagaments no pagats/abonats/anul·lats/saldats de les factures del
        # contracte, inclosos els que estan "En compromís". Els pagaments negatius
        # no hi resten: el deute d'un contracte no pot ser mai negatiu.
        debt_view = ContractDebtView.objects.filter(contract_token=obj.token).first()
        return debt_view.debt_amount if debt_view else 0
    
    def get_total_in_commitment_deposits(self, obj):
        commitment_deposit_status_cancelled_token = ConfigProject.objects.get(token='commitment_deposit_status_cancelled_token').value
        commitments = obj.commitment_deposits.exclude(status__token=commitment_deposit_status_cancelled_token).distinct()
        if commitments:
            return sum(comm.remaining for comm in commitments)
        return 0
    
    def get_total_debt_payments(self, obj):
        payment_status_expired = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_expired_token').value)
        payment_status_returned = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_returned_token').value)
        contract_payments = Payment.objects.filter(invoice__contract=obj, status__in=[payment_status_expired,payment_status_returned])
        return contract_payments.count()
    
    def get_person_important_observations(self, obj):
        from coredata.models import PersonObservation
        from coredata.serializers import PersonObservationSerializer
        holder_observations = PersonObservation.objects.filter(is_important=True, is_active=True, person=obj.holder)
        tenant_observations = PersonObservation.objects.filter(is_important=True, is_active=True, person=obj.tenant)
        owner_observations = PersonObservation.objects.filter(is_important=True, is_active=True, person=obj.owner)
        return PersonObservationSerializer(holder_observations | tenant_observations | owner_observations, many=True, context=self.context).data
    
    def get_supply_point_ids(self, obj):
        supply_points = obj.supply_points.all()
        return [supply_point.id for supply_point in supply_points]
    
    def get_supply_points(self, obj):
        supply_points = obj.supply_points.all()
        return SupplyPointMinimalSerializer(supply_points, many=True, read_only=True).data
    
    def get_price_rates(self, obj):
        price_rates = obj.price_rates.all().order_by('price_rate__product__position')
        return ContractPriceRateSerializer(price_rates, many=True, read_only=True).data

    def get_tarifa_bop(self, obj):
        from contract.utils.contract_service import get_contract_tarifa_bop
        return get_contract_tarifa_bop(obj)
    
    def get_registration_price_rates(self, obj):
        from pricing.serializers.price_rate_serializer import PriceRateSerializer
        registration_price_rates = obj.registration_price_rates.all()
        return PriceRateSerializer(registration_price_rates, many=True, read_only=True).data
    
    def get_show_price_rates(self, obj):
        from pricing.serializers.price_rate_serializer import PriceRateSerializer
        contract_price_rates = obj.price_rates.all().order_by('price_rate__product__position')
        serialized_price_rates = []
        for cr_price_rate in contract_price_rates:
            serialized_price_rate = {
                'id': cr_price_rate.id,
                'price_rate': PriceRateSerializer(cr_price_rate.price_rate).data,
                'supply_point': SupplyPointMinimalSerializer(cr_price_rate.supply_point).data,
                'is_bop_reference': cr_price_rate.is_bop_reference,
            }
            serialized_price_rates.append(serialized_price_rate)
        
        return serialized_price_rates
    
    def get_active_contract_termination(self, obj):
        from contract.models import ContractTerminationRequest
        contract_termination_cancelled_token = ConfigProject.objects.get(token='contract_termination_cancelled_token').value
        contract_termination_finished_token = ConfigProject.objects.get(token='contract_termination_completed_token').value
        contract_terminations = ContractTerminationRequest.objects.filter(contract=obj).exclude(status__token__in=[contract_termination_cancelled_token, contract_termination_finished_token])
        return contract_terminations.count() > 0
    
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
    
    def get_active_vulnerability_requests(self, obj):
        vulnerability_pending_token = ConfigProject.objects.get(token='vulnerability_request_status_pending_token').value
        vulnerability_requests = obj.vulnerability_requests.filter(status__token=vulnerability_pending_token)
        return vulnerability_requests.count() > 0
    
    def get_incidents(self, obj):
            return obj.incidents.all().count()
        
    def get_active_commitment_deposits(self, obj):
        deposit_paid_token = ConfigProject.objects.get(token='commitment_deposit_status_paid_token').value
        deposit_cancelled_token = ConfigProject.objects.get(token='commitment_deposit_status_cancelled_token').value
        commitment_deposits = obj.commitment_deposits.exclude(status__token__in=[deposit_paid_token, deposit_cancelled_token])
        
        return commitment_deposits.count()

    def get_active_claim_requests(self, obj):
        from claimrequest.models import ClaimRequestStatus, ClaimRequest
        
        pending_claim = ConfigProject.objects.get(token='claim_request_status_pending_token').value
        accepted_claim = ConfigProject.objects.get(token='claim_request_status_accepted_token').value
        claim_requests = ClaimRequest.objects.filter(payments__contract=obj, status__token__in=[pending_claim, accepted_claim])
        return claim_requests.count() > 0
    
    def get_calendar_tasks(self, obj):
        from notification.serializers.calendar_task_serializer import CalendarTaskSerializer
        return CalendarTaskSerializer(obj.calendar_tasks.all().order_by('-set_date'), many=True, read_only=True, context=self.context).data
    
    def get_invoices(self, obj):
        return []
    
    def get_observations_count(self, obj):
        return obj.observations.filter(is_active=True).count()

    def get_call_register_count(self, obj):
        return obj.call_registers.count()

    def get_communications_count(self, obj):
        return obj.communications.filter(is_active=True).count()

    def get_invoices_count(self, obj):
        invoice_type_token = ConfigProject.objects.get(token='invoice_type_invoice_token').value
        request_invoices = Invoice.objects.filter(contract_request=obj.contract_request, is_active=True, type__token=invoice_type_token, contract_request__isnull=False)
        unique_invoices = list(set(request_invoices.values_list('id', flat=True)) | set(obj.invoices.filter(is_active=True, type__token=invoice_type_token).values_list('id', flat=True)))
        return len(unique_invoices)

    def get_general_invoices_count(self, obj):
        return obj.general_invoices.filter(is_active=True).count()

    def get_members_change_count(self, obj):
        return LogContractTotalMembers.objects.filter(object=obj).count()
    
    def get_orders_count(self, obj):
        return obj.orders.count()
    
    def validate_total_persons(self, value):
        """Les persones a l'habitatge no poden ser 0 ni negatives: amb 0 la
        facturació peta (divisió per zero al càlcul de consum responsable).
        Els casos especials s'han de reflectir amb una variable del contracte."""
        if value is not None and value < 1:
            raise serializers.ValidationError(
                _("El nombre de persones a l'habitatge ha de ser com a mínim 1. "
                  "Si cal reflectir un cas especial, afegiu-ho com a variable del contracte.")
            )
        return value

    def update(self, instance, validated_data):
        representatives_save = validated_data.pop('representatives_save', None)
        debt_management_id = validated_data.pop('debt_management_id', None)
        address_billing_id = validated_data.pop('address_billing_id', None)
        address_contact_id = validated_data.pop('address_contact_id', None)
        person_contact_email_id = validated_data.pop('person_contact_email_id', None)
        phone_ids = validated_data.pop('phone_ids', None)
        sms_phone_ids = validated_data.pop('sms_phone_ids', None)
        contract_use_type = validated_data.pop('contract_use_type', None)
        contract_client_type = validated_data.pop('contract_client_type', None)
        price_rates_ids = validated_data.pop('price_rates_ids', None)
        registration_price_rates_ids = validated_data.pop('registration_price_rates_ids', None)
        category_id = validated_data.pop('category_id', None)
        company_id = validated_data.pop('company_id', None)
        total_persons = validated_data.pop('total_persons', None)
        remittance_date_provided = 'remittance_date' in validated_data
        remittance_date = validated_data.pop('remittance_date', None)
        simplified_invoice = validated_data.pop('simplified_invoice', None)
        communication_type = validated_data.pop('communication_type', None)
        new_task = validated_data.pop('new_task', None)
        payment_id = validated_data.pop('payment_id', None)
        holder_id_provided = 'holder_id' in validated_data
        holder_id = validated_data.pop('holder_id', None)
        owner_id_provided = 'owner_id' in validated_data
        owner_id = validated_data.pop('owner_id', None)
        
        use_type_id = validated_data.pop('use_type_id', None)
        contract_request_type_id = validated_data.pop('contract_request_type_id', None)
        
        print("use_type_id", use_type_id)
        print("contract_request_type_id", contract_request_type_id)
        
        mandate_id = validated_data.pop('mandate_id', None)
        mandate_id_overwrite = validated_data.pop('mandate_id_overwrite', False)
        registration_date = validated_data.pop('registration_date', None)
        request = self.context.get('request')
        user = request.user if request else None
        
        if new_task:
            task = CalendarTask.objects.get(id=new_task)
            task.contract = instance
            task.save()
        
            
        if contract_request_type_id is not None:
            contract_request_type = ContractRequestType.objects.get(id=contract_request_type_id)
            instance.contract_request_type = contract_request_type
        
        if communication_type is not None:
            instance.communication_type = communication_type
        
        if debt_management_id:
            if debt_management_id != 'null':
                debt_management = ContractDebtManagement.objects.get(id=debt_management_id)
                instance.debt_management = debt_management
            else:
                instance.debt_management = None
        
        if remittance_date_provided:
            instance.remittance_date = remittance_date
        
        if total_persons is not None:
            instance.total_persons = total_persons
        
        """ if mandate_id is not None and instance.payment:
            print("mandate_id", mandate_id)
            print("mandate_id_overwrite", mandate_id_overwrite)
            if not mandate_id_overwrite:
                mandate_id = generate_mandate_id(instance, instance.token)
            GeneralPaymentMandateLog.objects.create(
                general_payment=instance.payment, 
                previous_mandate_id=instance.payment.mandate_id if instance.payment else None,
                new_mandate_id=mandate_id,
                user=self.context['request'].user, 
                is_manual=mandate_id_overwrite)
            instance.payment.mandate_id = mandate_id
            instance.payment.save() """
        
        if registration_date is not None:
            instance.registration_date = registration_date
        
        if address_billing_id:
            address_billing = PersonAddress.objects.get(id=address_billing_id)
            instance.address_billing = address_billing
            
        if address_contact_id:
            address_contact = PersonAddress.objects.get(id=address_contact_id)
            instance.address_contact = address_contact
        
        if person_contact_email_id:
            person_contact_email = PersonContact.objects.get(id=person_contact_email_id)
            instance.person_contact_email = person_contact_email
        else:
            instance.person_contact_email = None
            if instance.communication_type == 'DIGITAL':
                instance.communication_type = 'PAPER'
        
        if phone_ids is not None:
            log_contract_phones_change(user, instance, phone_ids)
            phones = PersonContact.objects.filter(id__in=phone_ids)
            instance.contacts.clear()
            instance.contacts.add(*phones)
        
        if sms_phone_ids is not None:
            sms_phones = PersonContact.objects.filter(id__in=sms_phone_ids)
            instance.person_contact_sms.clear()
            instance.person_contact_sms.add(*sms_phones)
        
        if contract_use_type:
            contract_use_type = ContractUseType.objects.get(id=contract_use_type)
            instance.use_type = contract_use_type
        
        if use_type_id is not None:
            # Overwrite use type update
            print("Overwrite use type update")
            use_type = ContractUseType.objects.get(id=use_type_id)
            instance.use_type = use_type
            print("Use type updated: ", instance.use_type.name)
        
        if contract_client_type:
            contract_client_type = ContractClientType.objects.get(id=contract_client_type)
            instance.client_type = contract_client_type

        if representatives_save is not None:
            instance.representatives.clear()
            for representative_data in representatives_save:
                ContractRepresentative.objects.create(contract=instance, **representative_data)
        
        if price_rates_ids is not None:
            old_price_rates = list(instance.price_rates.all())
            instance.price_rates.clear()
            use_general_price_rates = validated_data.get('use_general_price_rates', instance.use_general_price_rates)
            instance.use_general_price_rates = use_general_price_rates
            for price_rate in price_rates_ids:
                price_rate_instance = PriceRate.objects.get(id=price_rate.get('price_rate').get('id'))
                supply_point_instance = SupplyPoint.objects.get(id=price_rate.get('supply_point').get('id'))
                try:
                    contract_price_rate, created = ContractPriceRate.objects.get_or_create(
                        price_rate=price_rate_instance, 
                        supply_point=supply_point_instance
                        )
                except:
                    contract_price_rate = ContractPriceRate.objects.filter(
                        price_rate=price_rate_instance, 
                        supply_point=supply_point_instance
                    ).first()
                if use_general_price_rates:
                    if instance.supply_point_default_id == supply_point_instance.id:
                        instance.price_rates.add(contract_price_rate)
                else:
                    instance.price_rates.add(contract_price_rate)
            
            new_price_rates = list(instance.price_rates.all())
            old_ids = set(pr.id for pr in old_price_rates if pr.id)
            new_ids = set(pr.id for pr in new_price_rates if pr.id)
            
            if old_ids != new_ids:
                old_map = { (pr.supply_point_id, pr.price_rate.product_id): pr.price_rate for pr in old_price_rates if pr.price_rate }
                new_map = { (pr.supply_point_id, pr.price_rate.product_id): pr.price_rate for pr in new_price_rates if pr.price_rate }
                
                changes_msgs = []
                all_keys = set(old_map.keys()) | set(new_map.keys())
                
                for key in all_keys:
                    old_pr = old_map.get(key)
                    new_pr = new_map.get(key)
                    
                    if (old_pr and not new_pr) or (not old_pr and new_pr) or (old_pr and new_pr and old_pr.id != new_pr.id):
                        old_txt = f"{old_pr.product.name} - {old_pr.name}" if old_pr and old_pr.product else _("None")
                        new_txt = f"{new_pr.product.name} - {new_pr.name}" if new_pr and new_pr.product else _("None")
                        
                        changes_msgs.append(
                            _("Old rate: %(old)s") % {'old': old_txt} + "\n" +
                            _("New rate: %(new)s") % {'new': new_txt}
                        )
                
                if changes_msgs:
                    observation_msg = "\n\n".join(changes_msgs)
                    ContractObservation.objects.create(
                        contract=instance,
                        observation=observation_msg,
                        user=user,
                        status=instance.status
                    )
        
        if registration_price_rates_ids is not None:
            instance.registration_price_rates.clear()
            registration_price_rates = PriceRate.objects.filter(id__in=registration_price_rates_ids)
            instance.registration_price_rates.add(*registration_price_rates)
            
        if category_id:
            category = ContractCategory.objects.get(id=category_id)
            instance.category = category

        initial = getattr(self, "initial_data", None) or {}
        if "company_id" not in initial and "company" in initial:
            raw = initial.get("company")
            if raw is None or raw == "":
                company_id = None
            elif isinstance(raw, dict):
                company_id = raw.get("id")
            else:
                try:
                    company_id = int(raw)
                except (TypeError, ValueError):
                    company_id = None
        if "company_id" in initial or "company" in initial:
            if company_id:
                instance.company = Company.objects.get(pk=company_id)
            else:
                instance.company = None

        if simplified_invoice != None:
            instance.simplified_invoice = simplified_invoice
        
        if 'is_pinned' in validated_data:
            print("is_pinned")
            print(validated_data.get('is_pinned'))
            pinned_contract = Contract.objects.filter(user_pinned=user).first()
            if pinned_contract:
                if pinned_contract.id == instance.id:
                    instance.user_pinned = None
                else:
                    instance.user_pinned = user
                    if not instance.user_checked.filter(id=user.id).exists():
                        instance.user_checked.add(user)
                    pinned_contract.user_pinned = None
                    pinned_contract.save()
            else:
                instance.user_pinned = user
        if 'is_checked' in validated_data:
            if user:
                if user not in instance.user_checked.all():
                    instance.user_checked.add(user)
                else:
                    instance.user_checked.remove(user)
        # Reassignacio directa de titular/propietari. No es una subrogacio: aqui nomes
        # canvia la persona del rol, mai el pagament ni les adreces ni els contactes.
        for role, provided, new_person_id in (
            ('holder', holder_id_provided, holder_id),
            ('owner', owner_id_provided, owner_id),
        ):
            if not provided:
                continue

            previous_person = getattr(instance, role)
            previous_person_id = previous_person.id if previous_person else None
            if previous_person_id == new_person_id:
                continue

            if role == 'holder' and not new_person_id:
                raise serializers.ValidationError({'holder_id': _("El contracte ha de tenir titular.")})

            new_person = Person.objects.get(id=new_person_id) if new_person_id else None
            setattr(instance, role, new_person)

            # La guardiola es del titular: si canvia el titular, ha de seguir-lo.
            if role == 'holder' and instance.piggy_bank:
                instance.piggy_bank.person = new_person
                instance.piggy_bank.save()

            role_label = _("titular") if role == 'holder' else _("propietari")
            ContractObservation.objects.create(
                contract=instance,
                observation=_("Canvi de %(role)s: %(previous)s -> %(new)s") % {
                    'role': role_label,
                    'previous': person_full_name(previous_person),
                    'new': person_full_name(new_person),
                },
                user=user,
                status=instance.status
            )
            ContractLog.objects.create(
                contract=instance,
                field_name=role,
                old_value=str(previous_person_id) if previous_person_id else None,
                new_value=str(new_person.id) if new_person else None,
                user=user
            )

        payment_data = self.initial_data.get('payment') if not isinstance(self.initial_data.get('payment'), (int, str)) else None
        if payment_id:
            from billing.models import GeneralPayment
            payment = GeneralPayment.objects.get(id=payment_id)
            instance.payment = payment
        elif payment_data:
            if instance.payment:
                payment_serializer = GeneralPaymentSerializer(instance.payment, data=payment_data, partial=True, context=self.context)
            else:
                payment_serializer = GeneralPaymentSerializer(data=payment_data, context=self.context)
            payment_serializer.is_valid(raise_exception=True)
            instance.payment = payment_serializer.save()
        instance.save()
        
        if price_rates_ids is not None:
            fill_contract_use_aca(single_contract_id=instance.id)
        return instance


def compute_contract_debt_amounts(contract_ids):
    """Deute per contracte (mateixa definicio que el detall i que vw_contract_debt)."""
    return contract_debt_amounts_by_contract_id(contract_ids)


class ContractMinimalListListSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        iterable = data.all() if hasattr(data, "all") else data
        contract_ids = [obj.pk for obj in iterable]
        self.child.context["debt_by_contract"] = compute_contract_debt_amounts(contract_ids)
        return super().to_representation(data)


class ContractMinimalListSerializer(serializers.ModelSerializer):
    debt_amount = serializers.SerializerMethodField()
    supply_point_default_status_token = serializers.CharField(source='supply_point_default.status.token', read_only=True)
    meter_code = serializers.CharField(source='supply_point_default.meter.code', read_only=True, allow_null=True)
    use_type_name = serializers.CharField(source='use_type.name', read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    holder_name = serializers.CharField(source='holder.name', read_only=True)
    holder_token = serializers.CharField(source='holder.token', read_only=True)
    holder_surname = serializers.CharField(source='holder.surname', read_only=True)
    holder_id = serializers.IntegerField(read_only=True)
    owner_id = serializers.IntegerField(read_only=True)
    tenant_id = serializers.IntegerField(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    client_type = serializers.CharField(source='client_type.name', read_only=True)
    active_contract_termination = serializers.BooleanField(read_only=True)
    is_pinned = serializers.SerializerMethodField()
    is_checked = serializers.SerializerMethodField()
    person_role = serializers.SerializerMethodField()
    previous_daily_consumption = serializers.SerializerMethodField()        # NECESSARY FOR EXTERNAL FUNCTIONS
    previous_period_consumption = serializers.SerializerMethodField()        # NECESSARY FOR EXTERNAL FUNCTIONS
    prefered_communication_type = serializers.SerializerMethodField()        # NECESSARY FOR EXTERNAL FUNCTIONS
    important_observations = serializers.SerializerMethodField()
    
    is_fire = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Contract
        list_serializer_class = ContractMinimalListListSerializer
        fields = [
            'id',
            'token',
            'created_at',
            'supply_point_default_status_token',
            'meter_code',
            'use_type_name',
            'status_name',
            'status_color',
            'holder_token',
            'holder_name',
            'holder_surname',
            'holder',
            'tenant',
            'owner',
            'holder_id',
            'tenant_id',
            'owner_id',
            'category_name',
            'client_type',
            'active_contract_termination',
            'block_billing',
            'contacts',
            'debt_amount',
            'termination_date',
            'is_pinned',
            'is_checked',
            'person_role',
            'important_observations',
            'is_fire',
            'previous_daily_consumption',
            'previous_period_consumption',
            'prefered_communication_type',
        ]
    
    def get_prefered_communication_type(self, obj):
        return {
            'type': obj.communication_type,
            'value': obj.person_contact_email.email if obj.person_contact_email and obj.communication_type == 'DIGITAL' else str(obj.address_contact.address) if obj.address_contact and obj.communication_type == 'PAPER' else None
        }
    
    def get_previous_daily_consumption(self, obj):
        # Prefetched on list; evaluate once instead of exists()+order_by() per row.
        stats = list(obj.consumption_stats.all())
        if not stats:
            return None
        latest = max(stats, key=lambda s: (s.year or 0, s.period or 0))
        return latest.daily_consumption

    def get_previous_period_consumption(self, obj):
        stats = obj.consumption_stats.all()
        current_year = datetime.datetime.now().year
        current_month = datetime.datetime.now().month
        candidates = [
            s for s in stats
            if s.year == current_year - 1
            and s.period is not None
            and current_month - 1 <= s.period <= current_month + 1
        ]
        if not candidates:
            return None
        best = max(candidates, key=lambda s: (s.year or 0, s.period or 0))
        return best.daily_consumption
    
    def get_important_observations(self, obj):
        observations = getattr(obj, 'prefetched_important_observations', None)
        if observations is None:
            observations = obj.observations.filter(is_important=True, is_active=True)
        return ContractObservationSerializer(observations, many=True, context=self.context).data
    
    def get_debt_amount(self, obj):
        debt_by_contract = self.context.get("debt_by_contract")
        if debt_by_contract is not None:
            return debt_by_contract.get(obj.pk, 0)
        return compute_contract_debt_amounts([obj.pk]).get(obj.pk, 0)
    
    def get_is_checked(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        if not user:
            return False
        # .filter().exists() bypasses the prefetch cache — iterate instead.
        return any(u.id == user.id for u in obj.user_checked.all())
    
    def get_is_pinned(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        return obj.user_pinned is not None and obj.user_pinned.id == user.id if user else False
    
    def get_person_role(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        person_id = request.query_params.get('persons')
        if not person_id:
            return None
        
        try:
            p_id = int(person_id.split(',')[0])
        except (ValueError, IndexError):
            return None
            
        roles = []
        if obj.holder_id == p_id:
            roles.append('HOLDER')
        if obj.owner_id == p_id:
            roles.append('OWNER')
        if obj.tenant_id == p_id:
            roles.append('TENANT')
        
        return roles if roles else None
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        # Comprovem que holder no sigui None abans d'accedir als seus atributs
        if instance.holder:
            holder_token = instance.holder.token or ''
            holder_name = instance.holder.name or ''
            holder_surname = instance.holder.surname or ''
            representation['holder_full_name'] = f"{holder_name} {holder_surname}".strip()
            representation['holder_vulnerability_level'] = instance.holder.vulnerability_level
        else:
            representation['holder_full_name'] = ''
            representation['holder_vulnerability_level'] = None
            
        if instance.tenant:
            tenant_token = instance.tenant.token or ''
            tenant_name = instance.tenant.name or ''
            tenant_surname = instance.tenant.surname or ''
            representation['tenant_token'] = tenant_token
            representation['tenant_full_name'] = f"{tenant_name} {tenant_surname}".strip()
        if instance.owner:
            owner_token = instance.owner.token or ''
            owner_name = instance.owner.name or ''
            owner_surname = instance.owner.surname or ''
            representation['owner_token'] = owner_token
            representation['owner_full_name'] = f"{owner_name} {owner_surname}".strip()
            
        representation['tenant_vulnerability_level'] = instance.tenant.vulnerability_level if instance.tenant else None
        representation['owner_vulnerability_level'] = instance.owner.vulnerability_level if instance.owner else None
        
        representation['communication_missing'] = False
        representation['email_missing'] = False
        if instance.communication_type == 'DIGITAL':
            if not instance.person_contact_email:
                representation['email_missing'] = True
                # Use prefetch cache (.exists() would hit the DB per row).
                if not instance.person_contact_sms.all():
                    representation['communication_missing'] = True
                
            if instance.person_contact_email and (instance.person_contact_email.email == '' or not instance.person_contact_email.email):
                representation['communication_missing'] = True
        elif instance.communication_type == 'PAPER':
            if not instance.address_contact:
                representation['communication_missing'] = True
                
        
        try:
            supply_point = instance.supply_point_default
            if supply_point:
                representation['supply_point'] = f"{ str(supply_point.address) }"
        except:
            print("supply_point not loaded")
        
        return representation
    
class ContractListSerializer(serializers.ModelSerializer):
    supply_point_default_id = serializers.CharField(source='supply_point_default.id', read_only=True)
    supply_point_default_token = serializers.CharField(source='supply_point_default.token', read_only=True)
    supply_point_default_status_token = serializers.CharField(source='supply_point_default.status.token', read_only=True)
    supply_point_ids = serializers.SerializerMethodField()
    debt_amount = serializers.SerializerMethodField()
    use_type_token = serializers.CharField(source='use_type.token', read_only=True)
    use_type_name = serializers.CharField(source='use_type.name', read_only=True)
    status_token = serializers.CharField(source='status.token', read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    owner_token = serializers.CharField(source='owner.token', read_only=True)
    tenant_token = serializers.CharField(source='tenant.token', read_only=True)
    holder_id = serializers.IntegerField(source='holder.id', read_only=True)
    holder_token = serializers.CharField(source='holder.token', read_only=True)
    holder_name = serializers.CharField(source='holder.name', read_only=True)
    holder_surname = serializers.CharField(source='holder.surname', read_only=True)
    payment_token = serializers.CharField(source='payment.token', read_only=True, allow_null=True)
    category_token = serializers.CharField(source='category.token', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    client_type = serializers.CharField(source='client_type.name', read_only=True)
    debt_management_token = serializers.CharField(source='debt_management.token', read_only=True)
    debt_management_name = serializers.CharField(source='debt_management.name', read_only=True)
    expired_invoices = serializers.SerializerMethodField()
    active_contract_termination = serializers.BooleanField(read_only=True)
    is_pinned = serializers.SerializerMethodField()
    is_checked = serializers.SerializerMethodField()
    
    is_fire = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Contract
        fields = [
            'id',
            'token',
            'created_at',
            'use_type_token',
            'use_type_name',
            'status_token',
            'status_name',
            'status_color',
            'supply_point_default_id',
            'supply_point_default_token',
            'supply_point_default_status_token',
            'owner_token',
            'tenant_token',
            'holder_id',
            'holder_token',
            'holder_name',
            'holder_surname',
            'payment_token',
            'category_token',
            'category_name',
            'client_type',
            'debt_management_token',
            'debt_management_name',
            'expired_invoices',
            'active_contract_termination',
            'block_billing',
            'supply_point_ids',
            'contacts',
            'debt_amount',
            'termination_date',
            'last_debt_data',
            'is_pinned',
            'is_checked',
            'is_fire',
        ]
    
    def get_expired_invoices(self, obj):
        # Prefer annotation when present (annotate_contract_list_expired_invoices).
        annotated = getattr(obj, 'expired_invoices', None)
        if annotated is not None and not callable(annotated):
            return annotated
        return 0
    
    def get_debt_amount(self, obj):
        payment_status_expired = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_expired_token').value)
        payment_status_returned = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_returned_token').value)
        payment_status_irrecoverable = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_irrecoverable_token').value)
        payment_status_endowment = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_endowment_token').value)
        contract_payments = Payment.objects.filter(
            invoice__contract=obj, 
            status__in=[payment_status_expired, payment_status_returned, payment_status_irrecoverable, payment_status_endowment]
            )
        payments_amount = contract_payments.aggregate(total=Sum('amount'))['total'] or 0
        return payments_amount
    
    def get_is_checked(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        return obj.user_checked.filter(id=user.id).exists() if user else False
    
    def get_is_pinned(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        return obj.user_pinned is not None and obj.user_pinned.id == user.id if user else False
    
    def get_supply_point_ids(self, obj):
        return [sp.id for sp in obj.supply_points.all()]
    
    
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        # Comprovem que holder no sigui None abans d'accedir als seus atributs
        if instance.holder:
            holder_name = instance.holder.name or ''
            holder_surname = instance.holder.surname or ''
            representation['holder_full_name'] = f"{holder_name} {holder_surname}".strip()
            representation['holder_vulnerability_level'] = instance.holder.vulnerability_level
        else:
            representation['holder_full_name'] = ''
            representation['holder_vulnerability_level'] = None
            
        representation['tenant_vulnerability_level'] = instance.tenant.vulnerability_level if instance.tenant else None
        representation['owner_vulnerability_level'] = instance.owner.vulnerability_level if instance.owner else None
        
        representation['communication_missing'] = False
        representation['email_missing'] = False
        if instance.communication_type == 'DIGITAL':
            if not instance.person_contact_email:
                representation['email_missing'] = True
                if not instance.person_contact_sms.exists():
                    representation['communication_missing'] = True
                
            if instance.person_contact_email and (instance.person_contact_email.email == '' or not instance.person_contact_email.email):
                representation['communication_missing'] = True
        elif instance.communication_type == 'PAPER':
            if not instance.address_contact:
                representation['communication_missing'] = True
                
        
        try:
            supply_point = instance.supply_point_default
            if supply_point:
                representation['supply_point'] = f"{ str(supply_point.address) }"
        except:
            print("supply_point not loaded")
        
        return representation

"""
Serialitzador mínim de contracte que retorna:
- id: Identificador del contracte
- token: Token únic del contracte
- holder_token: Token del titular del contracte
- holder: Nom complet del titular (afegit a to_representation)
- supply_point: Adreça del punt de subministrament (afegit a to_representation)
"""
class ContractMinimalSerializer(serializers.ModelSerializer):
    holder_token = serializers.CharField(read_only=True, source='holder.token')
    holder_id = serializers.CharField(read_only=True, source='holder.id')
    status_token = serializers.CharField(read_only=True, source='status.token')
    status_name = serializers.CharField(read_only=True, source='status.name')
    status_color = serializers.CharField(read_only=True, source='status.color')
    owner_id = serializers.CharField(read_only=True, source='owner.id')
    tenant_id = serializers.CharField(read_only=True, source='tenant.id')
    total_piggy_bank = serializers.SerializerMethodField()
    
    is_fire = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Contract
        fields = [
            'id', 'token', 'holder_token', 
            'holder_id', 'supply_points', 'status_token', 
            'status_name', 'status_color', 'owner_id', 
            'tenant_id', 'total_piggy_bank', 'created_at', 'termination_date',
            'is_fire'
            ]

    def get_total_piggy_bank(self, instance):
        if instance.piggy_bank:
            return instance.piggy_bank.amount
        return 0

    def get_supply_points(self, instance):
        return SupplyPointMinimalSerializer(instance.supply_points.all(), many=True, read_only=True).data

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        # Comprovem que holder no sigui None abans d'accedir als seus atributs
        if instance.holder:
            holder_name = instance.holder.name or ''
            holder_surname = instance.holder.surname or ''
            representation['holder'] = f"{holder_name} {holder_surname}".strip()
        else:
            representation['holder'] = ''
        
        supply_point = SupplyPoint.objects.filter(id = instance.supply_point_default_id).first()
        if supply_point:
            representation['supply_point'] = str(supply_point.address)
        
        return representation
class ContractMinimalNoSuppliesSerializer(serializers.ModelSerializer):
    holder_token = serializers.CharField(read_only=True, source='holder.token')
    holder_id = serializers.CharField(read_only=True, source='holder.id')
    status_token = serializers.CharField(read_only=True, source='status.token')
    status_name = serializers.CharField(read_only=True, source='status.name')
    status_color = serializers.CharField(read_only=True, source='status.color')
    owner_id = serializers.CharField(read_only=True, source='owner.id')
    tenant_id = serializers.CharField(read_only=True, source='tenant.id')
    total_piggy_bank = serializers.SerializerMethodField()
    
    class Meta:
        model = Contract
        fields = [
            'id', 'token', 'holder_token', 
            'holder_id', 'status_token', 
            'status_name', 'status_color', 'owner_id', 
            'tenant_id', 'total_piggy_bank', 'termination_date'
            ]

    def get_total_piggy_bank(self, instance):
        if instance.piggy_bank:
            return instance.piggy_bank.amount
        return 0

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        # Comprovem que holder no sigui None abans d'accedir als seus atributs
        if instance.holder:
            holder_name = instance.holder.name or ''
            holder_surname = instance.holder.surname or ''
            representation['holder'] = f"{holder_name} {holder_surname}".strip()
        else:
            representation['holder'] = ''
        
        supply_point = SupplyPoint.objects.filter(id = instance.supply_point_default_id).first()
        if supply_point:
            representation['supply_point'] = str(supply_point.address)
        
        return representation


class ContractGeneralInvoiceSerializer(serializers.ModelSerializer):
    holder_token = serializers.CharField(read_only=True, source='holder.token')
    holder_id = serializers.CharField(read_only=True, source='holder.id')
    payment = GeneralPaymentSerializer(read_only=True, required=False, allow_null=True)
    status_token = serializers.CharField(read_only=True, source='status.token')
    status_name = serializers.CharField(read_only=True, source='status.name')
    status_color = serializers.CharField(read_only=True, source='status.color')
    owner_id = serializers.CharField(read_only=True, source='owner.id')
    owner_token = serializers.CharField(read_only=True, source='owner.token')
    tenant_token = serializers.CharField(read_only=True, source='tenant.token')
    tenant_id = serializers.CharField(read_only=True, source='tenant.id')
    
    class Meta:
        model = Contract
        fields = [
            'id', 'token', 'holder_token', 
            'holder_id', 'supply_points', 'status_token', 
            'status_name', 'status_color', 'owner_token', 
            'tenant_token', 'tenant_id', 'owner_id', 'payment'
            ]

    def get_supply_points(self, instance):
        return SupplyPointMinimalSerializer(instance.supply_points.all(), many=True, read_only=True).data

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        if instance.holder:
            holder_name = instance.holder.name or ''
            holder_surname = instance.holder.surname or ''
            representation['holder'] = f"{holder_name} {holder_surname}".strip()
        else:
            representation['holder'] = ''
        
        supply_point = SupplyPoint.objects.filter(id = instance.supply_point_default_id).first()
        if supply_point:
            representation['supply_point'] = str(supply_point.address)
        
        return representation


class ContractWithPaymentsSerializer(serializers.ModelSerializer):
    status = ContractStatusSerializer(read_only=True, required=False, allow_null=True)

    category = serializers.CharField(source='category.name', read_only=True, allow_null=True)
    client_type = serializers.CharField(source='client_type.name', read_only=True, allow_null=True)
    use_type = serializers.CharField(source='use_type.name', read_only=True, allow_null=True)
    debt_management = serializers.CharField(source='debt_management.name', read_only=True, allow_null=True)

    expired_invoices = serializers.SerializerMethodField()
    # use_type = ContractUseTypeSerializer(read_only=True, required=False, allow_null=True)
    # client_type = ContractClientTypeSerializer(read_only=True, required=False, allow_null=True)
    # category = ContractCategorySerializer(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Contract
        fields = [
            'id', 'token', 'status', 
            'use_type', 'client_type', 'category', 
            'debt_management', 'expired_invoices'
            ]
        
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        filters = self.context.get('payment_filters', None)
        payments = Payment.objects.filter(invoice__contract=instance)

        if filters:
            payments = payments.filter(filters)

        # Excloure pagaments especificats
        payments_ignored = self.context.get('payments_ignored', None)
        if payments_ignored:
            payments = payments.exclude(id__in=payments_ignored)
        
        representation['payments'] = ContractPaymentSerializer(payments, many=True).data
        representation['payments_count'] = payments.count()
        representation['total_amount'] = payments.aggregate(total=Sum('amount'))['total'] or 0
        
        # Comprovem que holder no sigui None abans d'accedir als seus atributs
        if instance.holder:
            holder_name = instance.holder.name or ''
            holder_surname = instance.holder.surname or ''
            representation['holder'] = f"{holder_name} {holder_surname}".strip()
            representation['holder_token'] = instance.holder.token
        else:
            representation['holder'] = ''
            representation['holder_token'] = None
        
        if instance.holder and not instance.holder.is_juridic:
            representation['vulnerability_level'] = instance.holder.vulnerability_level
        elif instance.tenant and instance.holder.is_juridic:
            representation['vulnerability_level'] = instance.tenant.vulnerability_level

        return representation
    
    def get_expired_invoices(self, obj):
        invoices = Invoice.objects.filter(contract=obj, status=InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_expired_token').value))

        return_fee_invoice_ids = self.context.get('exclude_return_fee_invoice_ids')
        if return_fee_invoice_ids:
            invoices = invoices.exclude(id__in=return_fee_invoice_ids)

        return invoices.count()
    