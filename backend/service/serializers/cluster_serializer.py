from django.conf import settings
from rest_framework import serializers
from django_filters import rest_framework as filters
from auth.serializers import UserMinimalSerializer
from coredata.models import City, PostalCode, Street, StreetNumber, StreetNumberType, StreetType
from coredata.serializers import StreetSerializer, StreetNumberSerializer, PostalCodeSerializer, CitySerializer
from service.serializers.property_serializer import PropertyListSerializer, PropertySerializer
from coredata.utils.name_utils import generate_token, check_token_exists
from service.utils.property_route_service import auto_assign_route_to_property
from ..models import Cluster, ClusterObservation, ClusterNozzle, ClusterStatus, Connection, Property, Route, RoutePosition
from .value_objects_serializer import ClusterStatusSerializer, ClusterDocumentationFileSerializer
from .connection_serializer import ConnectionReducedSerializer, ConnectionSerializer
from .cluster_nozzle_serializer import ClusterNozzleSerializer, ClusterNozzleSaveSerializer

from urllib.parse import quote
from urllib.parse import urljoin

class ClusterObservationSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)
    
    class Meta:
        model = ClusterObservation
        fields = '__all__'

class ClusterSerializer(serializers.ModelSerializer):
    connection = ConnectionReducedSerializer(required=False, allow_null=True)
    nozzles = serializers.SerializerMethodField()
    status = ClusterStatusSerializer(required=False, allow_null=True)
    address_street = StreetSerializer(required=False, allow_null=True)
    address_street_number = StreetNumberSerializer(required=False, allow_null=True)
    address_postal_code = PostalCodeSerializer(required=False, allow_null=True)
    address_city = CitySerializer(required=False, allow_null=True)
    property = PropertyListSerializer(required=False, allow_null=True)
    documentation_files = ClusterDocumentationFileSerializer(many=True, read_only=True, required=False)

    class Meta:
        model = Cluster
        fields = '__all__'
    
    def get_nozzles(self, obj):
        nozzles = obj.nozzles.all().order_by('position')
        return ClusterNozzleSerializer(nozzles, many=True).data
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['address'] = f'{str(instance.address_street)} {str(instance.address_street_number)}'
        
        if instance.report_file:
            representation['report_file'] = self.build_absolute_uri(instance.report_file.url)
        
        return representation
    
    def build_absolute_uri(self, url):
        request = self.context.get('request')
        if request is not None:
            return request.build_absolute_uri(quote(url))
        return urljoin(settings.MEDIA_URL, quote(url))

class ClusterSaveSerializer(serializers.ModelSerializer):
    token = serializers.CharField(required=False, allow_blank=True)
    report_file_delete = serializers.BooleanField(write_only=True, required=False, allow_null=True)
    connection = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    # address_street = StreetSerializer(required=False, allow_null=True)
    # address_street_number = StreetNumberSerializer(required=False, allow_null=True)

    address_street_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    address_street_name = serializers.CharField(write_only=True, required=False, allow_null=True)
    address_street_type_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    address_street_type_abbreviation = serializers.CharField(write_only=True, required=False, allow_null=True)


    address_street_number_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    address_street_number_number = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    address_street_number_number_end = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    address_street_number_number_suffix = serializers.CharField(write_only=True, required=False, allow_null=True)
    address_street_number_number_end_suffix = serializers.CharField(write_only=True, required=False, allow_null=True)
    address_street_number_type = serializers.CharField(write_only=True, required=False, allow_null=True)

    address_postal_code_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    address_city_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    property_cadastral = serializers.CharField(write_only=True, required=False, allow_null=True)
    route = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    
    class Meta:
        model = Cluster
        fields = '__all__'
        
    def validate_address_city(self, value):
        if value is None:
            return None
        try:
            city = City.objects.get(id=value)
        except City.DoesNotExist:
            raise serializers.ValidationError(f"City with id {value} does not exist.")
        return city
    def validate_address_postal_code(self, value):
        if value is None:
            return None
        try:
            postal_code = PostalCode.objects.get(id=value)
        except PostalCode.DoesNotExist:
            raise serializers.ValidationError(f"PostalCode with id {value} does not exist.")
        return postal_code

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['address'] = f'{str(instance.address_street)} {str(instance.address_street_number)}'
        
        if instance.report_file:
            representation['report_file'] = self.build_absolute_uri(instance.report_file.url)
        
        return representation

    def build_absolute_uri(self, url):
        request = self.context.get('request')
        if request is not None:
            return request.build_absolute_uri(quote(url))
        return urljoin(settings.MEDIA_URL, quote(url))
    
    def create(self, validated_data):
        connection_data = validated_data.pop('connection', None)

        street_id = validated_data.pop('address_street_id', None)
        street_name = validated_data.pop('address_street_name', None)
        street_type_id = validated_data.pop('address_street_type_id', None)
        street_type_abbreviation = validated_data.pop('address_street_type_abbreviation', None)

        street_number_id = validated_data.pop('address_street_number_id', None)
        street_number_number = validated_data.pop('address_street_number_number', None)
        street_number_number_end = validated_data.pop('address_street_number_number_end', None)
        street_number_number_suffix = validated_data.pop('address_street_number_number_suffix', None)
        street_number_number_end_suffix = validated_data.pop('address_street_number_number_end_suffix', None)
        street_number_type = validated_data.pop('address_street_number_type', None)
        
        city_id = validated_data.pop('address_city_id', None)
        postal_code_id = validated_data.pop('address_postal_code_id', None)
        
        city = None
        postal_code = None

        if city_id:
            city = City.objects.get(id=city_id)
        if postal_code_id:
            postal_code = PostalCode.objects.get(id=postal_code_id)

        street = None
        street_type = None

        if street_id:
            street = Street.objects.get(id=street_id)
        else:
            if street_type_id:
                street_type = StreetType.objects.get(id=street_type_id)
            elif street_type_abbreviation:
                street_type = StreetType.objects.get(abbreviation=street_type_abbreviation)
            
            if street_type:
                street, _ = Street.objects.get_or_create(
                    name=street_name,
                    type=street_type,
                    city=city
                )
        
        
        street_number = None
        if street_number_type:
            number_type = StreetNumberType.objects.get(type=street_number_type)
            if number_type:
                if street_number_id:
                    street_number = StreetNumber.objects.get(id=street_number_id)
                else:
                    street_number = StreetNumber.objects.create(
                        street=street,
                        number=street_number_number,
                        number_end=street_number_number_end,
                        number_suffix=street_number_number_suffix,
                        number_end_suffix=street_number_number_end_suffix,
                        number_type=number_type
                    )

        route_position = None
        if(validated_data.get('route')):
            route = Route.objects.get(id=validated_data.pop('route'))
            route_position = RoutePosition.objects.create(
                position=0,
                route=route,
                token=route.token + '/' + str(street) + '-' + str(street_number_number) + '-' + str(postal_code),
                address_street=street,
                address_street_number=street_number,
                address_city=city,
                address_postal_code=postal_code,
                latitude=None,
                longitude=None,
                notebook = None,
                reader_observation = None
            )
        
        prop_token = generate_token(Property, args=['PROPN'])
        prop_token = check_token_exists(prop_token, Property)
        status = ClusterStatus.objects.get(is_default=True)
        property = Property.objects.create(
            token = prop_token,
            cadastral = validated_data.pop('property_cadastral', None),
            name = (str(street) + ' ' + str(street_number) + ' ' + str(postal_code)).strip(),
            route_position = route_position if route_position else None,
            address_street = street,
            address_street_number = street_number,
            address_city = city,
            address_postal_code = postal_code,
            latitude = None,
            longitude = None,
            is_active = True
        )
        if not route_position:
            auto_assign_route_to_property(property)
        cluster = Cluster.objects.create(
            status = status,
            address_street = street,
            address_street_number = street_number,
            address_city = city,
            address_postal_code = postal_code,
            property = property,
            **validated_data
        )

        if connection_data:
            connection = Connection.objects.get(id=connection_data)
            if connection:
                cluster.connection = connection
                connection.clusters.add(cluster)
                connection.save()
        cluster.save()
        return cluster

    def update(self, instance, validated_data):

        print(validated_data)

        connection_data = validated_data.pop('connection', None)
        
        street_id = validated_data.pop('address_street_id', None)
        street_name = validated_data.pop('address_street_name', None)
        street_type_id = validated_data.pop('address_street_type_id', None)
        street_type_abbreviation = validated_data.pop('address_street_type_abbreviation', None)

        street_number_id = validated_data.pop('address_street_number_id', None)
        street_number_number = validated_data.pop('address_street_number_number', None)
        street_number_number_end = validated_data.pop('address_street_number_number_end', None)
        street_number_number_suffix = validated_data.pop('address_street_number_number_suffix', None)
        street_number_number_end_suffix = validated_data.pop('address_street_number_number_end_suffix', None)
        street_number_type = validated_data.pop('address_street_number_type', None)

        city_id = validated_data.pop('address_city_id', None)
        postal_code_id = validated_data.pop('address_postal_code_id', None)
        
        route = validated_data.pop('route', None)
        
        if route:
            instance.route = route
        
        city = None
        postal_code = None

        if city_id:
            city = City.objects.get(id=city_id)
        if postal_code_id:
            postal_code = PostalCode.objects.get(id=postal_code_id)

        instance.address_city = city
        instance.address_postal_code = postal_code

        if street_id:
            street = Street.objects.get(id=street_id)
            if street:
                instance.address_street = street
            else:
                instance.address_street = None
        else:
            street_type = None
            if street_type_id:
                street_type = StreetType.objects.get(id=street_type_id)
            elif street_type_abbreviation:
                street_type = StreetType.objects.get(abbreviation=street_type_abbreviation)
            
            if street_type:
                street, _ = Street.objects.get_or_create(
                    name=street_name,
                    type=street_type,
                    city=city
                )
                instance.address_street = street


        if street_number_id:
            street_number = StreetNumber.objects.get(id=street_number_id)
            if street_number:
                instance.address_street_number = street_number
            else:
                instance.address_street_number = None
        elif street_number_type:
            number_type = StreetNumberType.objects.get(type=street_number_type)
            if number_type:
                street_number = StreetNumber.objects.create(
                    street=instance.address_street,
                    number=street_number_number,
                    number_end=street_number_number_end,
                    number_suffix=street_number_number_suffix,
                    number_end_suffix=street_number_number_end_suffix,
                    number_type=number_type
                )
                instance.address_street_number = street_number

        if connection_data:
            connection = Connection.objects.get(id=connection_data)
            if connection:
                instance.connection = connection
            else:
                instance.connection = None
        else:
            instance.connection = None

        

        if validated_data.get('report_file_delete'):
            instance.report_file.delete(save=False)
            instance.report_file = None
            validated_data.pop('report_file_delete') 

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update nozzles if they are in initial_data
        nozzles_data = self.initial_data.get('nozzles', None)
        if nozzles_data is not None:
            if isinstance(nozzles_data, str):
                import json
                try:
                    nozzles_data = json.loads(nozzles_data)
                except Exception:
                    nozzles_data = []

            if isinstance(nozzles_data, list):
                for nozzle_data in nozzles_data:
                    if isinstance(nozzle_data, str):
                        import json
                        try:
                            nozzle_data = json.loads(nozzle_data)
                        except Exception:
                            continue

                    if isinstance(nozzle_data, dict):
                        nozzle_id = nozzle_data.get('id')
                        if nozzle_id:
                            try:
                                nozzle_instance = ClusterNozzle.objects.get(id=nozzle_id, cluster=instance)
                                if 'supply_points' in nozzle_data and isinstance(nozzle_data['supply_points'], list) and len(nozzle_data['supply_points']) > 0:
                                    first_sp = nozzle_data['supply_points'][0]
                                    nozzle_data_copy = dict(nozzle_data)
                                    nozzle_data_copy['supplyPoint'] = first_sp
                                    nozzle_data_copy['supply_point_id'] = first_sp.get('id')
                                else:
                                    nozzle_data_copy = nozzle_data
                                
                                nozzle_serializer = ClusterNozzleSaveSerializer(
                                    nozzle_instance,
                                    data=nozzle_data_copy,
                                    partial=True,
                                    context=self.context
                                )
                                if nozzle_serializer.is_valid():
                                    nozzle_serializer.save()
                                else:
                                    raise serializers.ValidationError(nozzle_serializer.errors)
                            except ClusterNozzle.DoesNotExist:
                                pass

        return instance
    
    def validate(self, data):
        if not self.instance and 'token' not in data:
            raise serializers.ValidationError({"token": "This field is required."})
        
        if data.get('report_file_delete') == None: 
            if 'report_file_delete' in data:
                data.pop('report_file_delete')
        
        return data
    

class ClusterListSerializer(serializers.ModelSerializer):
    status_token = serializers.CharField(source='status.token', read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    connection_name = serializers.CharField(source='connection.name', read_only=True)
    connection_token = serializers.CharField(source='connection.token', read_only=True)
    connection_id = serializers.CharField(source='connection.id', read_only=True)
    street = serializers.CharField(source='address_street', read_only=True)
    street_number = serializers.CharField(source='address_street_number', read_only=True)
    class Meta:
        model = Cluster
        fields = [
            'id',
            'token',
            'created_at',
            'status_token',
            'status_name',
            'status_color',
            'nb_nozzles',
            'connection_name',
            'connection_token',
            'connection_id',
            'street',
            'street_number'
        ]
