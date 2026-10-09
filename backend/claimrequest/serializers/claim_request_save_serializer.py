from datetime import datetime, timedelta
import uuid
from rest_framework import serializers
from django.utils import timezone
from django.db.models import Sum, Count, Q
from coredata.models import ConfigProject
from coredata.utils.name_utils import generate_token
from logger.models import LogClaimRequestContractChange
from contract.models import Contract, ContractClientType, ContractDebtManagement, ContractRequest, ContractRequestStatus, ContractStatus, ContractUseType
from notification.models import CalendarTask
from service.models import RouteZone
from ..models import ClaimRequest, ClaimRequestStatus, ClaimRequestPayment
from billing.models import Payment

class ClaimRequestSaveSerializer(serializers.ModelSerializer):
    contract_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    payment_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    ignore_payment_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    ignore_contract_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    status_token = serializers.CharField(write_only=True, required=False, allow_null=True)
    end_step_date = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    
    class Meta:
        model = ClaimRequest
        fields = '__all__'
    
    def validate_end_step_date(self, value):
        if value == '' or value is None:
            return None
        try:
            # Intentem primer amb el format ISO 8601 amb Z
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                # Si falla, provem amb el format estàndard
                return datetime.fromisoformat(value)
        except ValueError:
            raise serializers.ValidationError(
                "Format de data incorrecte. Utilitza el format: YYYY-MM-DDThh:mm[:ss[.uuuuuu]][+HH:MM|-HH:MM|Z]"
            )
    
    def create(self, validated_data):
        contract_ids = validated_data.pop('contract_ids', None)
        payment_ids = validated_data.pop('payment_ids', None)
        ignore_payment_ids = validated_data.pop('ignore_payment_ids', None)
        ignore_contract_ids = validated_data.pop('ignore_contract_ids', None)
        step_id = validated_data.get('step', None)
        
        request = self.context.get('request')
        user = request.user if request else None
        print("user")
        print(user)
        
        validated_data['user'] = user
        
        random_uuid = uuid.uuid4()
        validated_data['token'] = generate_claim_id()      #generate_token(ClaimRequest)
        
        if not validated_data.get('name'):
            validated_data['name'] = f"Solicitud de reclamació {validated_data['token']}"
        
        status_pending = ClaimRequestStatus.objects.get(token=ConfigProject.objects.get(token='claim_request_status_pending_token').value)
        validated_data['status'] = status_pending

        if contract_ids:
            contracts = Contract.objects.filter(id__in=contract_ids).distinct('id')
            validated_data['contracts'] = contracts
        
        # Crear el ClaimRequest
        claim_request = super(ClaimRequestSaveSerializer, self).create(validated_data)
        
        # Crear els ClaimRequestPayment per cada pagament
        claim_payments = []
        payment_status_paid_token = ConfigProject.objects.get(token='payment_status_paid_token').value
        if payment_ids:
            payments = Payment.objects.filter(
                id__in=payment_ids).exclude(
                    id__in=ignore_payment_ids).exclude(
                        invoice__contract__id__in=ignore_contract_ids)
            for payment in payments:
                claim_payment = ClaimRequestPayment(
                    claim_request=claim_request,
                    payment=payment,
                    contract=payment.invoice.contract if payment.invoice else None,
                    is_paid=payment.status and payment.status.token == payment_status_paid_token,
                    is_vulnerable=False,
                )
                claim_payments.append(claim_payment)
        
        ClaimRequestPayment.objects.bulk_create(claim_payments)

        if claim_payments:
            from claimrequest.tasks import (
                claim_request_groups_payments_without_rates,
                create_joined_payments_for_claim_request,
            )
            if claim_request_groups_payments_without_rates(claim_request):
                create_joined_payments_for_claim_request(claim_request)
        
        return claim_request
    
    def update(self, instance, validated_data):
        status_token = validated_data.pop('status_token', None)
        contract_ids = validated_data.pop('contract_ids', None)
        new_step = validated_data.pop('current_step', None)
        end_step_date = validated_data.pop('end_step_date', None)
        request = self.context.get('request')
        user = request.user if request else None
        
        if contract_ids:
            # Obtenim els ClaimRequestPayment que tenen els contractes que volem eliminar
            claim_payments_to_remove = instance.payments.filter(contract__id__in=contract_ids)
            
            # Eliminem els ClaimRequestPayment
            for claim_payment in claim_payments_to_remove:
                LogClaimRequestContractChange.objects.create(
                    object=instance,
                    deleted_contract=claim_payment.contract,
                    user=user,
                )
                claim_payment.delete()
        
        if status_token:
            new_status = ClaimRequestStatus.objects.get(token=status_token)
            LogClaimRequestContractChange.objects.create(
                    object=instance,
                    previous_status=instance.status,
                    current_status=new_status,
                    user=user,
                )
            instance.status = new_status

        if end_step_date:
            instance.current_step.end_step_date = end_step_date
            instance.current_step.save()
        
        if new_step:
            previous_due_date = instance.current_step.due_date
            today = datetime.now()
            instance.current_step = new_step
            day_type = instance.current_step.duration_type
            if day_type == 'WORK':
                due_date = add_working_days(today, instance.current_step.duration or 0)
            else:
                due_date = today + timedelta(days=instance.current_step.duration or 0)
            
            calendar_task = {
                'token': uuid.uuid4(),
                'name': f"Gestió d'impagats {instance.token}",
                'description': f"Finalitzar pas de {instance.current_step.name} a la gestió d'impagats {instance.token}",
                'color': 'yellow',
                'set_date': due_date,
                'is_active': True,
                'user': instance.user,
            }
            CalendarTask.objects.create(**calendar_task)
            
            instance.current_step.due_date = due_date
            instance.current_step.save()
        
        instance.save()
        
        return instance 

class ExcludeContractSerializer(serializers.Serializer):
    request_id = serializers.IntegerField(required=True)
    contract_id = serializers.IntegerField(required=True) 


def add_working_days(start_date, work_days):
    current_date = start_date
    added_days = 0
    while added_days < work_days:
        current_date += timedelta(days=1)
        if current_date.weekday() < 5: 
            added_days += 1
    return current_date

def generate_claim_id():
    current_year = datetime.now().strftime('%y')
    total = ClaimRequest.objects.filter(created_at__year=datetime.now().year).count()
    ident = str(total).zfill(9)
    return current_year + ident