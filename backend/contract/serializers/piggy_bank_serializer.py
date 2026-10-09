from rest_framework import serializers

from billing.serializers.general_payment_serializer import GeneralPaymentSerializer
from contract.serializers.piggy_bank_movement_serializer import PiggyBankMovementSerializer
from coredata.models import ConfigProject
from coredata.serializers import PersonMinimalSerializer,PersonMinimalContractSerializer

from ..models import ( PiggyBank )

class PiggyBankSerializer(serializers.ModelSerializer):
    person = PersonMinimalSerializer(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = PiggyBank
        fields = '__all__'
    
    def to_representation(self, instance):
        from billing.models import Invoice
        representation = super().to_representation(instance)
        representation['movements'] = PiggyBankMovementSerializer(instance.movements.all().order_by('-movement_date', '-created_at'), many=True).data
        try:
            from contract.models import Contract
            contract = Contract.objects.get(piggy_bank=instance)
        except:
            contract = None
        representation['contract_token'] = contract.token if contract else None
        representation['contract_id'] = contract.id if contract else None
        representation['contract_status_name'] = contract.status.name if contract else None
        representation['contract_status_color'] = contract.status.color if contract else None
        representation['contract_holder'] = PersonMinimalContractSerializer(contract.holder).data if contract else None
        representation['contract_tenant'] = PersonMinimalContractSerializer(contract.tenant).data if contract and contract.tenant else None
        representation['contract_owner'] = PersonMinimalContractSerializer(contract.owner).data if contract and contract.owner else None
        representation['contract_payment'] = GeneralPaymentSerializer(contract.payment).data if contract else None
        
        if contract:
            budget_type_token = ConfigProject.objects.get(token='invoice_type_budget_token').value
            invoice_type_token = ConfigProject.objects.get(token='invoice_type_invoice_token').value
            invoices = Invoice.objects.filter(contract=contract, piggy_bank=instance, type__token=budget_type_token)
            invoice_data = []
            for invoice in invoices:
                try:
                    invoice_budget = Invoice.objects.get(budget_token=instance.token, type__token=invoice_type_token)
                except:
                    invoice_budget = None
                if not invoice_budget:
                    invoice_data.append({
                        'id': invoice.id,
                        'token': invoice.token,
                        'title_final': invoice.title_final,
                        'total_final': invoice.total_final,
                        'status_name': invoice.status.name,
                        'status_id': invoice.status.id,
                        'status_token': invoice.status.token,
                        'status_color': invoice.status.color,
                        'type_token': invoice.type.token,
                        'invoice_file_template': invoice.invoice_file_template is not None,
                        'invoice_file': invoice.invoice_file.id if invoice.invoice_file else None,
                    })
            representation['invoices'] = invoice_data
        return representation

class PiggyBankSaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = PiggyBank
        fields = '__all__'

class PiggyBankListSerializer(serializers.ModelSerializer):
    contract_token = serializers.CharField(source='contract.token', read_only=True)
    contract_id = serializers.IntegerField(source='contract.id', read_only=True)
    person_token = serializers.CharField(source='person.token', read_only=True)
    person_id = serializers.IntegerField(source='person.id', read_only=True)
    
    class Meta:
        model = PiggyBank
        fields = ['id', 'token', 'amount', 'contract_token', 'contract_id', 'person_token', 'person_id']
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['person_full_name'] = f"{instance.person.name} {instance.person.surname}"
        return representation

class PiggyBankMinimalSerializer(serializers.ModelSerializer):
    person_token = serializers.CharField(source='person.token', read_only=True)
    person_id = serializers.IntegerField(source='person.id', read_only=True)
    
    class Meta:
        model = PiggyBank
        fields = ['id', 'token', 'amount', 'person_token', 'person_id']
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['person_full_name'] = f"{instance.person.name} {instance.person.surname}"
        try:
            from contract.models import Contract
            contract = Contract.objects.get(piggy_bank=instance)
        except:
            contract = None
        representation['contract_token'] = contract.token if contract else None
        representation['contract_id'] = contract.id if contract else None
        return representation