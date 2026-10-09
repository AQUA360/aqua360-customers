from rest_framework import serializers
from django_filters import rest_framework as filters

from auth.serializers import UserMinimalSerializer
from ..models import ( Connection, ConnectionInstallationType, ConnectionObservation, ConnectionRequest, ConnectionStatus, Exploitation )
from coredata.serializers import StreetSerializer, StreetNumberSerializer, PostalCodeSerializer, CitySerializer
from .value_objects_serializer import ConnectionInstallationTypeSerializer, ConnectionStatusSerializer, ConnectionTypeSerializer, ConnectionUseTypeSerializer, ConnectionValveTypeSerializer, ConnectionDiameterSerializer, ConnectionMaterialSerializer, SupplyPointSupplyTypeSerializer, ConnectionDocumentationFileSerializer
from .exploitation_serializer import ExploitationSerializer
from .DMA_serializer import DMASerializer
from .tank_serializer import TankSerializer

class ConnectionObservationSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = ConnectionObservation
        fields = '__all__'

class ConnectionSerializer(serializers.ModelSerializer):
    exploitation = ExploitationSerializer(read_only=True, required=False, allow_null=True)
    status = ConnectionStatusSerializer(read_only=True, required=False, allow_null=True)
    type = ConnectionTypeSerializer(read_only=True, required=False, allow_null=True)
    use_type = ConnectionUseTypeSerializer(read_only=True, required=False, allow_null=True)
    installation_type = ConnectionInstallationTypeSerializer(read_only=True, required=False, allow_null=True)
    valve_type = ConnectionValveTypeSerializer(read_only=True, required=False, allow_null=True)
    diameter = ConnectionDiameterSerializer(read_only=True, required=False, allow_null=True)
    material = ConnectionMaterialSerializer(read_only=True, required=False, allow_null=True)
    dma = DMASerializer(read_only=True, required=False, allow_null=True)
    address_street = StreetSerializer(read_only=True, required=False, allow_null=True)
    address_street_number = StreetNumberSerializer(read_only=True, required=False, allow_null=True)
    address_postal_code = PostalCodeSerializer(read_only=True, required=False, allow_null=True)
    address_city = CitySerializer(read_only=True, required=False, allow_null=True)
    tank = TankSerializer(required=False, allow_null=True)
    supply_type = SupplyPointSupplyTypeSerializer(read_only=True, required=False, allow_null=True)
    documentation_files = ConnectionDocumentationFileSerializer(many=True, read_only=True, required=False)

    # write_only

    class Meta:
        model = Connection
        fields = '__all__'
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        address_complete = ""
        if(str(instance.address_street) and str(instance.address_street) != 'None'):
            address_complete += str(instance.address_street)
        if(str(instance.address_street_number) and str(instance.address_street_number) != 'None'):
            address_complete += ", " + str(instance.address_street_number)
        representation['address_complete'] = address_complete
        
        if instance.address_extra:
            representation['address_complete'] += " " + instance.address_extra
        
        if instance.clusters.exists():
            representation['clusters'] = [{"id": cluster.id, "token": cluster.token} for cluster in instance.clusters.all()]
        if instance.supply_points.exists():
            representation['supply_points'] = [{"id": sp.id, "token": sp.token} for sp in instance.supply_points.all()]
        
        representation['connection_request'] = None
        try:
            connection_request = ConnectionRequest.objects.get(connection=instance)
            representation['connection_request'] = {
                "id": connection_request.id,
                "token": connection_request.token
            }
        except ConnectionRequest.DoesNotExist:
            pass
        
        return representation


class ConnectionSaveSerializer(serializers.ModelSerializer):
    # mirem els camps obligatoris, per poder-los passar buits en l'edició (no create)
    token = serializers.CharField(required=False, allow_blank=True)
    class Meta:
        model = Connection
        fields = '__all__'
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        address_complete = ""
        if(str(instance.address_street) and str(instance.address_street) != 'None'):
            address_complete += str(instance.address_street)
        if(str(instance.address_street_number) and str(instance.address_street_number) != 'None'):
            address_complete += ", " + str(instance.address_street_number)
        representation['address_complete'] = address_complete
        representation['exploitation'] = ExploitationSerializer(instance.exploitation).data
        representation['status'] = ConnectionStatusSerializer(instance.status).data
        return representation
    def validate(self, data):
        if not self.instance and 'token' not in data:
            raise serializers.ValidationError({"token": "This field is required."})
        return data
    
    def create(self, validated_data):
        status = ConnectionStatus.objects.get(is_default=True)
        connection = super().create(validated_data)
        connection.status = status
        connection.save()
        
        if not connection.exploitation:
            exploitation_qs = Exploitation.objects.filter(is_active=True)
            if exploitation_qs.count() == 1:
                connection.exploitation = exploitation_qs.first()
                connection.save()
                    
        if connection.installation_type == None:
            connection.installation_type = ConnectionInstallationType.objects.get(is_default=True)
            connection.save()
        return connection
    
class ConnectionMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Connection
        fields = ['id', 'token']
        
class ConnectionListSerializer(serializers.ModelSerializer):
    status_token = serializers.CharField(source='status.token', read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    connection_name = serializers.CharField(source='connection.name', read_only=True)
    connection_token = serializers.CharField(source='connection.token', read_only=True)
    street = serializers.CharField(source='address_street', read_only=True)
    street_number = serializers.CharField(source='address_street_number', read_only=True)
    diameter_name = serializers.CharField(source='diameter.name', read_only=True)
    use_type_name = serializers.CharField(source='use_type.name', read_only=True)
    dma_name = serializers.CharField(source='dma.name', read_only=True)
    dma_token = serializers.CharField(source='dma.token', read_only=True)
    exploitation_name = serializers.CharField(source='exploitation.name', read_only=True)
    exploitation_token = serializers.CharField(source='exploitation.token', read_only=True)
    class Meta:
        model = Connection
        fields = [
            'id',
            'token',
            'created_at',
            'installation_at',
            'status_token',
            'status_name',
            'status_color',
            'connection_name',
            'connection_token',
            'street',
            'street_number',
            'address_extra',
            'diameter_name',
            'use_type_name',
            'dma_name',
            'dma_token',
            'exploitation_name',
            'exploitation_token'
        ]
        
class ConnectionReducedSerializer(serializers.ModelSerializer):
    exploitation = ExploitationSerializer(read_only=True, required=False, allow_null=True)
    status = ConnectionStatusSerializer(read_only=True, required=False, allow_null=True)
    
    address_street = StreetSerializer(read_only=True, required=False, allow_null=True)
    address_street_number = StreetNumberSerializer(read_only=True, required=False, allow_null=True)
    address_postal_code = PostalCodeSerializer(read_only=True, required=False, allow_null=True)
    address_city = CitySerializer(read_only=True, required=False, allow_null=True)

    # write_only

    class Meta:
        model = Connection
        fields = '__all__'
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        address_complete = ""
        if(str(instance.address_street) and str(instance.address_street) != 'None'):
            address_complete += str(instance.address_street)
        if(str(instance.address_street_number) and str(instance.address_street_number) != 'None'):
            address_complete += ", " + str(instance.address_street_number)
        representation['address_complete'] = address_complete
        
        return representation