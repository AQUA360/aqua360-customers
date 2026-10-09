import datetime
from rest_framework import serializers
from auth.serializers import UserMinimalSerializer

from billing.models import Invoice, InvoiceLog, InvoiceStatus, JoinedPayment, Payment, PaymentStatus
from billing.serializers.invoice_line_item_serializer import InvoiceLineItemSerializer
from billing.serializers.reading_serializer import ReadingMinimalSerializer
from billing.serializers.value_objects_serializer import (
    InvoiceSerieSerializer, InvoiceStatusSerializer, InvoiceSuppressionReasonSerializer, 
    InvoiceTypeSerializer, PaymentStatusSerializer, RejectMotiveSerializer, InvoiceWarningSerializer
)
from billing.utils.confirm_invoice_service import confirm_invoice
from billing.utils.payment_service import log_payment_status
from contract.serializers.contract_request_serializer import ContractRequestMinimalSerializer
from contract.serializers.contract_serializer import ContractMinimalSerializer, ContractSerializer
from statistics.serializers import BillingConsumptionSerializer
from verifactu.serializers.verifactu_serializer import VerifactuNotificationSerializer

from billing.utils.invoice_service import change_status_logger, get_totals
from billing.utils.invoice_list_queryset import invoice_list_config_tokens
from billing.utils.invoice_suppression_service import invoice_needs_return, suppress_invoice
from contract.serializers.contract_termination_request_serializer import ContractTerminationRequestMinimalSerializer
from coredata.models import ConfigProject
from pricing.serializers.value_objects_serializer import ProductOriginSerializer
from service.serializers.company_serializer import CompanySerializer
from service.serializers.connection_request_serializer import ConnectionRequestListSerializer
from service.serializers.exploitation_serializer import ExploitationSerializer
from billing.utils.message_service import invoice_add_messages
from verifactu.utils.notify_verifactu_service import notify_cancelled_invoices
from billing.serializers.billing_serializer import BillingListSerializer

class InvoiceSerializer(serializers.ModelSerializer):
    line_items = InvoiceLineItemSerializer(many=True, read_only=True, required=False, allow_null=True)
    type = InvoiceTypeSerializer(read_only=True, required=False, allow_null=True)
    serie = InvoiceSerieSerializer(read_only=True, required=False, allow_null=True)
    
    contract = ContractMinimalSerializer(read_only=True, required=False, allow_null=True)
    contract_request = ContractRequestMinimalSerializer(read_only=True, required=False, allow_null=True)
    contract_termination = ContractTerminationRequestMinimalSerializer(read_only=True, required=False, allow_null=True)
    """ reading = ReadingMinimalSerializer(read_only=True, required=False, allow_null=True)
    reading_last = ReadingMinimalSerializer(read_only=True, required=False, allow_null=True) """
    readings = ReadingMinimalSerializer(many=True, read_only=True, required=False, allow_null=True)
    origin = ProductOriginSerializer(read_only=True, required=False, allow_null=True)
    exploitation = ExploitationSerializer(read_only=True, required=False, allow_null=True)
    company = CompanySerializer(read_only=True, required=False, allow_null=True)
    status = InvoiceStatusSerializer(read_only=True, required=False, allow_null=True)
    billing = BillingListSerializer(read_only=True, required=False, allow_null=True)
    
    
    parent_invoice = serializers.SerializerMethodField()
    period_from = serializers.SerializerMethodField()
    period_to = serializers.SerializerMethodField()
    
    entity = serializers.SerializerMethodField()
    object_id = serializers.SerializerMethodField()
    type_token = serializers.CharField(source='type.token', read_only=True)
    
    class Meta:
        model = Invoice
        fields = '__all__'
        
    
    def get_parent_invoice(self, obj):
        if obj.parent_invoice:
            return {
                'id': obj.parent_invoice.id,
                'token': obj.parent_invoice.token,
                'status_name': obj.parent_invoice.status.name if obj.parent_invoice.status else None,
                'status_color': obj.parent_invoice.status.color if obj.parent_invoice.status else None,
                'total': obj.parent_invoice.total_final,
            }
        return None

    def get_period_to(self, obj):
        last_reading = obj.readings.order_by('-reading_date').first()
        return last_reading.reading_date if last_reading else None

    def get_period_from(self, obj):
        last_reading = obj.readings.order_by('-reading_date').first()
        if last_reading and obj.consumption_days:
            return last_reading.reading_date - datetime.timedelta(days=obj.consumption_days)
        return None

    def get_entity(self, obj):
        if obj.contract_termination:
            return "contract_termination_request"
        if obj.contract_request:
            return "contract_request"
        if obj.contract:
            return "contract"
        if obj.connection_request:
            return "connection_request"
        return None

    def get_object_id(self, obj):
        if obj.contract_termination:
            return obj.contract_termination.id
        if obj.contract_request:
            return obj.contract_request.id
        if obj.contract:
            return obj.contract.id
        if obj.connection_request:
            return obj.connection_request.id
        return None


class InvoiceMinimalBatchListSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        iterable = list(data.all() if hasattr(data, 'all') else data)
        tokens = invoice_list_config_tokens()
        budget_tokens = [
            obj.token for obj in iterable
            if obj.token and obj.type_id and obj.type and obj.type.token == tokens['budget']
        ]
        budget_invoice_by_token = {}
        if budget_tokens:
            try:
                linked = (
                    Invoice.objects.filter(
                        budget_token__in=budget_tokens,
                        type__token=tokens['invoice'],
                    )
                    .order_by('budget_token', '-created_at')
                    .distinct('budget_token')
                )
                for inv in linked:
                    budget_invoice_by_token[inv.budget_token] = inv
            except Exception:
                for inv in Invoice.objects.filter(
                    budget_token__in=budget_tokens,
                    type__token=tokens['invoice'],
                ).order_by('-created_at'):
                    budget_invoice_by_token.setdefault(inv.budget_token, inv)

        self.child.context['budget_invoice_by_token'] = budget_invoice_by_token
        self.child.context['invoice_list_tokens'] = tokens
        return [self.child.to_representation(item) for item in iterable]


class InvoiceMinimalSerializer(serializers.ModelSerializer):
    
    contract_is_vulnerable = serializers.SerializerMethodField()
    contract_id = serializers.CharField(read_only=True, source='contract.id')
    contract_token = serializers.CharField(read_only=True, source='contract.token')
    contract_request_token = serializers.CharField(read_only=True, source='contract_request.token')
    contract_termination_token = serializers.CharField(read_only=True, source='contract_termination.token')
    contract_termination_contract_token = serializers.CharField(read_only=True, source='contract_termination.contract.token')
    contract_termination_id = serializers.CharField(read_only=True, source='contract_termination.id')
    exploitation_token = serializers.CharField(read_only=True, source='exploitation.token')
    origin_name = serializers.CharField(read_only=True, source='origin.name')
    status_name = serializers.CharField(read_only=True, source='status.name')
    status_color = serializers.CharField(read_only=True, source='status.color')
    contract_piggy_bank = serializers.SerializerMethodField()
    person_piggy_bank = serializers.SerializerMethodField()
    period_from = serializers.SerializerMethodField()
    period_to = serializers.SerializerMethodField()
    paid_at = serializers.SerializerMethodField()
    entity = serializers.SerializerMethodField()
    object_id = serializers.SerializerMethodField()
    type_token = serializers.CharField(source='type.token', read_only=True)
    
    
    class Meta:
        model = Invoice
        list_serializer_class = InvoiceMinimalBatchListSerializer
        fields = '__all__'

    def _tokens(self):
        tokens = self.context.get('invoice_list_tokens')
        if tokens is None:
            tokens = invoice_list_config_tokens()
            self.context['invoice_list_tokens'] = tokens
        return tokens
    
    def get_paid_at(self, obj):
        tokens = self._tokens()
        if not (obj.status and obj.status.token in [tokens['paid'], tokens['payoff']]):
            return None
        payments = list(obj.payments.all())
        if not payments:
            return None
        # Prefetch is ordered by payment_date; first is earliest.
        return payments[0].payment_date
    
    def get_contract_piggy_bank(self, obj):
        if obj.contract and obj.contract.piggy_bank:
            return obj.contract.piggy_bank.amount
        return 0
    
    def get_person_piggy_bank(self, obj):
        if not obj.contract and (obj.connection_request or obj.contract_request):
            person = obj.connection_request.person if obj.connection_request else obj.contract_request.person if obj.contract_request else None
            if person and person.piggy_bank:
                return person.piggy_bank.amount
        return 0

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        payments = list(instance.payments.all())
        tokens = self._tokens()
        if instance.type and instance.type.token == tokens['budget']:
            budget_map = self.context.get('budget_invoice_by_token')
            invoice = budget_map.get(instance.token) if budget_map is not None else None
            if budget_map is None:
                invoice = (
                    Invoice.objects.filter(
                        budget_token=instance.token,
                        type__token=tokens['invoice'],
                    )
                    .order_by('-created_at')
                    .first()
                )
            if invoice:
                representation['invoice_budget'] = InvoiceIdListSerializer(invoice).data
        representation['excluded_payments'] = any(payment.is_excluded for payment in payments)
        
        return representation
    
    def get_contract_is_vulnerable(self, obj):
        vulnerable_token = self._tokens()['vulnerable']
        return obj.contract and obj.contract.debt_management and obj.contract.debt_management.token == vulnerable_token

    def _latest_reading(self, obj):
        readings = list(obj.readings.all())
        if not readings:
            return None
        # Prefetch ordered by -reading_date; otherwise pick max in Python.
        return readings[0]

    def get_period_to(self, obj):
        last_reading = self._latest_reading(obj)
        return last_reading.reading_date if last_reading else None

    def get_period_from(self, obj):
        last_reading = self._latest_reading(obj)
        if last_reading and obj.consumption_days:
            return last_reading.reading_date - datetime.timedelta(days=obj.consumption_days)
        return None

    def get_entity(self, obj):
        if obj.contract_termination:
            return "contract_termination_request"
        if obj.contract_request:
            return "contract_request"
        if obj.contract:
            return "contract"
        if obj.connection_request:
            return "connection_request"
        return None

    def get_object_id(self, obj):
        if obj.contract_termination:
            return obj.contract_termination.id
        if obj.contract_request:
            return obj.contract_request.id
        if obj.contract:
            return obj.contract.id
        if obj.connection_request:
            return obj.connection_request.id
        return None


class InvoiceIdListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = ['id', 'token', 'serie_final']
        
class InvoiceMinimalListSerializer(serializers.ModelSerializer):
    contract_token = serializers.CharField(read_only=True, source='contract.token')
    billing_consumption = BillingConsumptionSerializer(read_only=True)
    warning = InvoiceWarningSerializer(read_only=True)

    period_from = serializers.SerializerMethodField()
    period_to = serializers.SerializerMethodField()
    use_type_final = serializers.SerializerMethodField()
    
    has_possible_leak_comm = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = '__all__'

    def get_period_to(self, obj):
        last_reading = obj.readings.order_by('-reading_date').first()
        return last_reading.reading_date if last_reading else None

    def get_period_from(self, obj):
        last_reading = obj.readings.order_by('-reading_date').first()
        if last_reading and obj.consumption_days:
            return last_reading.reading_date - datetime.timedelta(days=obj.consumption_days)
        return None

    def get_use_type_final(self, obj):
        if obj.contract and obj.contract.use_type:
            return {
                'id': obj.contract.use_type.id,
                'token': obj.contract.use_type.token,
                'name': obj.contract.use_type.name,
            }
        return None

    def get_has_possible_leak_comm(self, obj):
        cancelled_token = ConfigProject.objects.get(token='communication_process_status_cancelled_token').value
        return any([reading.communication_processes.exclude(status__token=cancelled_token).exists() for reading in obj.readings.filter(is_control=False)])
        # return obj.readings.filter(is_control=False).communication_processes.exclude(status__token=cancelled_token).exists()
        
class InvoiceSaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = '__all__'

class InvoiceFullSerializer(serializers.ModelSerializer):
    line_items = InvoiceLineItemSerializer(many=True, read_only=True, required=False, allow_null=True)
    contract = ContractMinimalSerializer(read_only=True, required=False, allow_null=True)
    contract_request = ContractRequestMinimalSerializer(read_only=True, required=False, allow_null=True)
    contract_termination = ContractTerminationRequestMinimalSerializer(read_only=True, required=False, allow_null=True)
    connection_request = ConnectionRequestListSerializer(read_only=True, required=False, allow_null=True)
    """ reading = ReadingMinimalSerializer(read_only=True, required=False, allow_null=True)
    reading_last = ReadingMinimalSerializer(read_only=True, required=False, allow_null=True) """
    readings = ReadingMinimalSerializer(many=True, read_only=True, required=False, allow_null=True)
    origin = ProductOriginSerializer(read_only=True, required=False, allow_null=True)
    exploitation = ExploitationSerializer(read_only=True, required=False, allow_null=True)
    company = CompanySerializer(read_only=True, required=False, allow_null=True)
    status = InvoiceStatusSerializer(read_only=True, required=False, allow_null=True)
    billing = BillingListSerializer(read_only=True, required=False, allow_null=True)
    serie = InvoiceSerieSerializer(read_only=True, required=False, allow_null=True)
    type = InvoiceTypeSerializer(read_only=True, required=False, allow_null=True)
    reject = RejectMotiveSerializer(read_only=True, required=False, allow_null=True)
    suppression_reason = InvoiceSuppressionReasonSerializer(read_only=True, required=False, allow_null=True)
    suppressed_by_username = serializers.CharField(read_only=True, source='suppressed_by.username')
    parent_invoice = serializers.SerializerMethodField()
    general_contracts = serializers.SerializerMethodField()
    verifactu_notification = VerifactuNotificationSerializer(read_only=True, required=False, allow_null=True)
    has_payments_piggy_bank = serializers.SerializerMethodField()
    billing_consumption = BillingConsumptionSerializer(read_only=True)
    warning = InvoiceWarningSerializer(read_only=True)
    period_from = serializers.SerializerMethodField()
    period_to = serializers.SerializerMethodField()
    entity = serializers.SerializerMethodField()
    object_id = serializers.SerializerMethodField()
    type_token = serializers.CharField(source='type.token', read_only=True)
    
    total_payments = serializers.SerializerMethodField()
    payment_in_remittance = serializers.SerializerMethodField()
    remittances = serializers.SerializerMethodField()
    joined_payments = serializers.SerializerMethodField()
    
    status_token = serializers.CharField(write_only=True, required=False, allow_null=True)
    delete_payments = serializers.BooleanField(write_only=True, required=False, allow_null=True)
    class Meta:
        model = Invoice
        fields = '__all__'
 

    def get_total_payments(self, obj):
        return obj.payments.count()
 
    def get_has_payments_piggy_bank(self, obj):
        if obj.left_to_pay != obj.total_final:
            payments = obj.payments.filter(
                piggy_bank_movements__isnull=False, piggy_bank_movements__is_positive=False)
            if payments.count() > 0:
                return True
        return False
            
    def get_payment_in_remittance(self, obj):
        # RETURN TRUE IF THERE IS A PAYMENT IN A REMITTANCE PENDING TO BE SENT
        for payment in obj.payments.all():
            if payment.remittances.filter(sent_at__isnull=False).exists():
                return True
        return False

    def get_remittances(self, obj):
        from billing.models import PaymentRemittance
        remittances = PaymentRemittance.objects.filter(payments__in=obj.payments.all()).order_by('-created_at')
        invoice_remittances = []
        for remittance in remittances:
            invoice_remittances.append({
                'id': remittance.id,
                'token': remittance.token,
                'sent_at': remittance.sent_at,
                'sent_by': remittance.sent_by.username if remittance.sent_by else None,
            })
        return invoice_remittances
    
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
    
    def get_general_contracts(self, obj):
        if obj.is_general:
            return [{'id': contract.id, 'token': contract.token} for contract in obj.general_contracts.all()]
        return []
          
    def to_representation(self, instance):
        subtotal, taxes, taxes_base, total = get_totals(instance)
        representation = super().to_representation(instance)
        
        child_invoices = Invoice.objects.filter(parent_invoice=instance)
        child_invoices_data = []
        for child_invoice in child_invoices:
            child_invoices_data.append({
                'id': child_invoice.id,
                'token': child_invoice.token,
                'serie_final': child_invoice.serie_final,
                'status_name': child_invoice.status.name if child_invoice.status else None,
                'status_color': child_invoice.status.color if child_invoice.status else None,
                'total': child_invoice.total_final,
            })
        representation['child_invoices'] = child_invoices_data
        
        representation['line_items'] = [
            line_item for line_item in representation['line_items'] if line_item.get('is_active', False)
        ]
        representation['subtotal'] = subtotal
        representation['taxes'] = taxes
        representation['taxes_base'] = taxes_base
        representation['total'] = total
        
        from billing.serializers.invoice_serializer import InvoiceMinimalSerializer
        invoice_type_token = ConfigProject.objects.get(token='invoice_type_invoice_token').value
        budget_type_token = ConfigProject.objects.get(token='invoice_type_budget_token').value
        invoice_cancel_token = ConfigProject.objects.get(token='invoice_status_cancelled_token').value
        if instance.type.token == budget_type_token:
            try:
                invoice = Invoice.objects.filter(budget_token=instance.token, type__token=invoice_type_token).order_by('-created_at').first()
                if invoice:
                    representation['invoice_budget'] = InvoiceMinimalSerializer(invoice).data
            except:
                pass
        elif instance.type.token == invoice_type_token:
            try:
                budget = Invoice.objects.get(token=instance.budget_token, type__token=budget_type_token)
                if budget:
                    representation['budget'] = InvoiceMinimalSerializer(budget).data
            except:
                pass
        
        try:
            if instance.return_token:
                return_invoice = Invoice.objects.get(token=instance.return_token, type__token=invoice_type_token)
                representation['return_invoice'] = { 'id': return_invoice.id, 'token': return_invoice.token, 'serie_final': return_invoice.serie_final }
            else:
                return_invoice = Invoice.objects.filter(return_token=instance.token, type__token=invoice_type_token).order_by('-created_at').first()
                if return_invoice:
                    representation['returned_invoice'] = { 'id': return_invoice.id, 'token': return_invoice.token, 'serie_final': return_invoice.serie_final }
        except:
            pass
        
        try:
            if instance.refactored_token and instance.refactored_token != "":
                refactored_invoice = Invoice.objects.get(token=instance.refactored_token, type__token=invoice_type_token)
                representation['refactored_invoice'] = { 'id': refactored_invoice.id, 'token': refactored_invoice.token, 'serie_final': refactored_invoice.serie_final }
            else:
                refactor_invoice = Invoice.objects.filter(refactored_token=instance.token, type__token=invoice_type_token).order_by('-created_at').first()
                if refactor_invoice:
                    representation['refactor_invoice'] = { 'id': refactor_invoice.id, 'token': refactor_invoice.token, 'serie_final': refactor_invoice.serie_final }
        except:
            pass
            
        return representation
    
    
    def get_parent_invoice(self, obj):
        if obj.parent_invoice:
            return {
                'id': obj.parent_invoice.id,
                'token': obj.parent_invoice.token,
                'serie_final': obj.parent_invoice.serie_final,
                'status_name': obj.parent_invoice.status.name if obj.parent_invoice.status else None,
                'status_color': obj.parent_invoice.status.color if obj.parent_invoice.status else None,
                'total': obj.parent_invoice.total_final,
            }
        return None
    
    def get_period_to(self, obj):
        last_reading = obj.readings.order_by('-reading_date').first()
        return last_reading.reading_date if last_reading else None

    def get_period_from(self, obj):
        last_reading = obj.readings.order_by('-reading_date').first()
        if last_reading and obj.consumption_days:
            return last_reading.reading_date - datetime.timedelta(days=obj.consumption_days)
        return None

    def get_entity(self, obj):
        if obj.contract_termination:
            return "contract_termination_request"
        if obj.contract_request:
            return "contract_request"
        if obj.contract:
            return "contract"
        if obj.connection_request:
            return "connection_request"
        return None

    def get_object_id(self, obj):
        if obj.contract_termination:
            return obj.contract_termination.id
        if obj.contract_request:
            return obj.contract_request.id
        if obj.contract:
            return obj.contract.id
        if obj.connection_request:
            return obj.connection_request.id
        return None
    
    def create(self, validated_data):
        instance = Invoice.objects.create(**validated_data)
        
        return instance
    
    def update(self, instance, validated_data):
        user = self.context['request'].user
        status_token = validated_data.pop('status_token', None)
        delete_payments = validated_data.pop('delete_payments', False)
        payments = instance.payments.all()
        
        do_confirm = False
        
        if status_token:
            cancelled_token = ConfigProject.objects.get(token='invoice_status_cancelled_token').value
            dropped_token = ConfigProject.objects.get(token='invoice_status_dropped_token').value
            status = InvoiceStatus.objects.get(token=status_token)
            # Una factura emesa no es pot anul·lar només canviant-ne l'estat: cal l'abonament (FR),
            # igual que a /billing/invoice/{id}/return/. Es retorna el saldo cobrat al moneder,
            # com feia check_cancel_invoice quan aquest camí només canviava l'estat.
            if status_token in [cancelled_token, dropped_token] and invoice_needs_return(instance):
                for attr, value in validated_data.items():
                    setattr(instance, attr, value)
                suppress_invoice(instance, user, return_paid_total=True, target_status=status)
                notify_cancelled_invoices([instance])
                return instance
            invoice_status_irrecoverable_token = ConfigProject.objects.get(token='invoice_status_irrecoverable_token').value
            invoice_status_endowment_token = ConfigProject.objects.get(token='invoice_status_endowment_token').value
            invoice_status_paid_token = ConfigProject.objects.get(token='invoice_status_paid_token').value
            invoice_status_confirmed_token = ConfigProject.objects.get(token='invoice_status_confirmed_token').value
            if status_token == invoice_status_irrecoverable_token:
                payment_status_irrecoverable_token = ConfigProject.objects.get(token='payment_status_irrecoverable_token').value
                payment_status_irrecoverable = PaymentStatus.objects.get(token=payment_status_irrecoverable_token)
                for payment in payments:
                    if payment.status != payment_status_irrecoverable:
                        log_payment_status(payment, payment_status_irrecoverable, user)
                payments.update(status=payment_status_irrecoverable)
                instance.is_active = False
            elif status_token == invoice_status_endowment_token:
                payment_status_endowment_token = ConfigProject.objects.get(token='payment_status_endowment_token').value
                payment_status_endowment = PaymentStatus.objects.get(token=payment_status_endowment_token)
                for payment in payments:
                    if payment.status != payment_status_endowment:
                        log_payment_status(payment, payment_status_endowment, user)
                payments.update(status=payment_status_endowment)
                instance.is_active = False
            elif status_token == invoice_status_confirmed_token and (not instance.status or instance.status.token != invoice_status_confirmed_token) and len(instance.payments.all()) == 0:
                do_confirm = True
            
            change_status_logger(user, instance, status)
            instance.status = status
            if status.token == cancelled_token:
                notify_cancelled_invoices([instance])
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        if delete_payments:
            
            payments.update(is_active=False)
        if do_confirm:
            confirm_invoice(instance)
        return instance
    
class InvoiceLogSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(read_only=True)
    
    class Meta:
        model = InvoiceLog
        fields = [
            'id',
            'created_at',
            'field_name',
            'old_value',
            'new_value',
            'operation_token',
            'user'
        ]