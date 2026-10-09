from django.conf import settings
from rest_framework import serializers
from coredata.serializers import PersonSerializer
from ..models import ContractTenantChange

class ContractTenantChangeSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = ContractTenantChange
        fields = '__all__'
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        representation['new_tenant'] = PersonSerializer(instance.new_tenant).data if instance.new_tenant else None
        representation['previous_tenant'] = PersonSerializer(instance.previous_tenant).data if instance.previous_tenant else None
        
        return representation
    
    def create(self, validated_data):
        from ..models import ContractObservation, ContractLog
        
        contract = validated_data.get('contract')
        if 'previous_tenant' not in validated_data and contract:
            validated_data['previous_tenant'] = contract.tenant
            
        tenant_change = ContractTenantChange.objects.create(**validated_data)
        
        contract.tenant = tenant_change.new_tenant
        contract.save()
        
        # Log the change
        request = self.context.get('request')
        user = request.user if request else None
        
        prev_name = f"{tenant_change.previous_tenant.name} {tenant_change.previous_tenant.surname}" if tenant_change.previous_tenant else "Cap"
        new_name = f"{tenant_change.new_tenant.name} {tenant_change.new_tenant.surname}" if tenant_change.new_tenant else "Cap"
        
        observation_msg = f"Canvi de llogater: {prev_name} -> {new_name}"
        
        ContractObservation.objects.create(
            contract=contract,
            observation=observation_msg,
            user=user,
            status=contract.status
        )
        
        # Optionally also Log it in the technical log
        ContractLog.objects.create(
            contract=contract,
            field_name="tenant",
            old_value=str(tenant_change.previous_tenant.id) if tenant_change.previous_tenant else None,
            new_value=str(tenant_change.new_tenant.id) if tenant_change.new_tenant else None,
            user=user
        )
        
        return tenant_change
    
    
    
    