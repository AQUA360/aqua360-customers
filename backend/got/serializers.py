import datetime
from django.db import transaction
from rest_framework import serializers
from auth.serializers import UserMinimalSerializer
from service.serializers.connection_request_serializer import ConnectionRequestListSerializer
from order.models import ( Order, OrderObservation, OrderStatus, Operator )
from service.serializers.supply_point_serializer import SupplyPointMinimalSerializer
from coredata.serializers import AddressMinimalSerializer, AddressSerializer
from order.serializers.value_objects_serializer import OrderStatusSerializer, OrderTypeSerializer, OrderTypeMinimalSerializer, OrderReasonMinimalSerializer
from order.serializers.operator_serializer import OperatorSerializer
from order.serializers.order_serializer import OrderObservationSerializer

class OrderGotObservationSerializer(serializers.ModelSerializer):    
    has_user = serializers.SerializerMethodField()
    def get_has_user(self, obj):
        object_user = obj.user
        if object_user:
            return True
        return False
    class Meta:
        model = OrderObservation
        fields = ['created_at','has_user', 'observation']
        

class ConnectionGotSerializer(serializers.Serializer):
    """Minimal Connection serializer for GOT app with only essential fields"""
    token = serializers.CharField(read_only=True)
    installation_at = serializers.DateField(read_only=True)
    code_gis = serializers.CharField(read_only=True)
    diameter = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    use_type = serializers.SerializerMethodField()
    installation_type = serializers.SerializerMethodField()
    supply_type = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    
    def get_diameter(self, obj):
        """Return diameter name as string"""
        return obj.diameter.name if obj.diameter else None
    
    def get_type(self, obj):
        """Return connection type name as string"""
        return obj.type.name if obj.type else None
    
    def get_use_type(self, obj):
        """Return use type name as string"""
        return obj.use_type.name if obj.use_type else None
    
    def get_installation_type(self, obj):
        """Return installation type name as string"""
        return obj.installation_type.name if obj.installation_type else None
    
    def get_supply_type(self, obj):
        """Return supply type name as string"""
        return obj.supply_type.name if obj.supply_type else None
    
    def get_address(self, obj):
        """Concatenate address fields into a single string"""
        address_parts = []
        
        if obj.address_street:
            # Get street type and name
            street_str = ""
            if obj.address_street.type:
                street_str += f"{obj.address_street.type.name} "
            if obj.address_street.name:
                street_str += obj.address_street.name
            if street_str:
                address_parts.append(street_str.strip())
        
        if obj.address_street_number:
            # Get street number - use the model's __str__ method or build manually
            number_str = ""
            if obj.address_street_number.number_type:
                if obj.address_street_number.number_type.type == 'N':
                    number_str = str(obj.address_street_number.number) if obj.address_street_number.number else ""
                elif obj.address_street_number.number_type.type == 'SN':
                    number_str = "S/N"
                elif obj.address_street_number.number_type.type == 'R':
                    number_str = f"{obj.address_street_number.number}-{obj.address_street_number.number_end}"
                elif obj.address_street_number.number_type.type == 'S':
                    number_str = f"{obj.address_street_number.number} {obj.address_street_number.number_suffix}"
            
            if number_str:
                address_parts.append(number_str)
        
        if obj.address_postal_code:
            address_parts.append(obj.address_postal_code.code)
        
        if obj.address_city:
            address_parts.append(obj.address_city.name)
        
        return ", ".join(address_parts) if address_parts else None

class OrderGotSerializer(serializers.ModelSerializer):
    supply_point = serializers.SerializerMethodField()
    connection = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    connection_request = ConnectionRequestListSerializer(read_only=True, required=False, allow_null=True)
    incident = serializers.SerializerMethodField()
    related_incidents = serializers.SerializerMethodField()
    observations = serializers.SerializerMethodField()
    total_reports = serializers.SerializerMethodField()
    check_response = serializers.SerializerMethodField()
    
    def get_supply_point(self, instance):
        if not instance.supply_point:
            return None
        return SupplyPointMinimalSerializer(instance.supply_point).data
        
    
    def get_observations(self, instance):
        """Serialize observations using OrderGotObservationSerializer"""
        observations = instance.observations.all()
        return OrderGotObservationSerializer(observations, many=True).data
    def get_connection(self, instance):
        if not instance.connection:
            return None
        return ConnectionGotSerializer(instance.connection).data
    
    def get_address(self, instance):
        if not instance.address:
            return None
        return AddressSerializer(instance.address).data
    
    def get_total_reports(self, instance):
        return instance.reports.count()
    
    def get_check_response(self, instance):
        return getattr(instance, 'check_response', None)
    
    def get_incident(self, instance):
        from notification.serializers.incident_serializer import IncidentListSerializer
        return IncidentListSerializer(instance.incident).data if instance.incident else None
    
    def get_contract(self, instance):
        from contract.serializers.contract_serializer import ContractMinimalSerializer
        return ContractMinimalSerializer(instance.contract).data if instance.contract else None

    def get_contract_request(self, instance):
        from contract.serializers.contract_request_serializer import ContractRequestSerializer
        return ContractRequestSerializer(instance.contract_request).data if instance.contract_request else None

    def get_related_incidents(self, obj):
        # Incidències que referencien l'ordre més la que l'ha originada
        from django.db.models import Q
        from notification.models import Incident
        return Incident.objects.filter(
            Q(order_incident=obj) | Q(orders=obj)
        ).distinct().count()

    contract_token = serializers.CharField(source='contract.token', read_only=True)
    contract_request_token = serializers.CharField(source='contract_request.token', read_only=True)
     
    operators = OperatorSerializer(many = True, read_only=True, required=False, allow_null=True)
    
    
    class Meta:
        model = Order
        fields = '__all__'
        
    def to_representation(self, instance):
        from order.serializers.value_objects_serializer import OrderPrioritySerializer
        representation = super().to_representation(instance)
        
        representation['type'] = OrderTypeMinimalSerializer(instance.type).data if instance.type else None
        representation['reason'] = OrderReasonMinimalSerializer(instance.reason).data if instance.reason else None
        representation['status'] = OrderStatusSerializer(instance.status).data
        representation['priority'] = OrderPrioritySerializer(instance.priority).data if instance.priority else None
        
        # Afegim el contract serialitzat
        if instance.contract:
            from contract.serializers.contract_serializer import ContractMinimalSerializer
            representation['contract'] = ContractMinimalSerializer(instance.contract).data
        
        return representation
