from rest_framework import serializers
from django_filters import rest_framework as filters
from coredata.models import City, PostalCode, Street, StreetNumber, StreetNumberType, StreetType
from coredata.serializers import StreetSerializer, StreetNumberSerializer, PostalCodeSerializer, CitySerializer
from ..models import ( Property, Route, RoutePosition )
from .route_serializer import RoutePositionSerializer
from ..utils.property_route_service import auto_assign_route_to_property, sync_property_tokens_with_route_position
from coredata.utils.name_utils import generate_token, check_token_exists

class PropertySerializer(serializers.ModelSerializer):
    route_position = RoutePositionSerializer(required=False, allow_null=True)
    address_street = StreetSerializer(required=False, allow_null=True)
    address_street_number = StreetNumberSerializer(required=False, allow_null=True)
    address_postal_code = PostalCodeSerializer(required=False, allow_null=True)
    address_city = CitySerializer(required=False, allow_null=True)

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
    route = serializers.IntegerField(write_only=True, required=False, allow_null=True)


    supply_points = serializers.SerializerMethodField()
    class Meta:
        model = Property
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

    def create(self, validated_data):
        route_id = validated_data.pop('route', None)
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

        if not validated_data.get('token'):
            prop_token = generate_token(Property, args=['PROPN'])
            validated_data['token'] = check_token_exists(prop_token, Property)

        if not validated_data.get('name'):
            validated_data['name'] = (str(street) + ' ' + str(street_number) + ' ' + (str(postal_code.code) if postal_code else '')).strip()

        print(validated_data)

        property = Property.objects.create(
            address_street = street,
            address_street_number = street_number,
            address_city = city,
            address_postal_code = postal_code,
            **validated_data
        )

        if route_id:
            route = Route.objects.get(id=route_id)
            route_position = RoutePosition.objects.create(
                position=0,
                route=route,
                token=route.token + '/' + str(street) + '-' + str(street_number) + '-' + (str(postal_code.code) if postal_code else ''),
                address_street=street,
                address_street_number=street_number,
                address_city=city,
                address_postal_code=postal_code,
            )
            property.route_position = route_position
            property.save()
            sync_property_tokens_with_route_position(route_position)
        else:
            auto_assign_route_to_property(property)
            property.save()

        return property

    def update(self, instance, validated_data):
        route_id = validated_data.pop('route', None)
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

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if route_id:
            route = Route.objects.get(id=route_id)
            route_position = RoutePosition.objects.create(
                position=0,
                route=route,
                token=route.token + '/' + str(instance.address_street) + '-' + str(instance.address_street_number) + '-' + (str(instance.address_postal_code.code) if instance.address_postal_code else ''),
                address_street=instance.address_street,
                address_street_number=instance.address_street_number,
                address_city=instance.address_city,
                address_postal_code=instance.address_postal_code,
            )
            instance.route_position = route_position
            instance.save()
            sync_property_tokens_with_route_position(route_position)
        else:
            auto_assign_route_to_property(instance)
            instance.save()

        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['address'] = str(instance.address_street) + ' ' + str(instance.address_street_number)
        return representation
    def get_route_position(self, obj):
        # Inclou només els camps essencials per trencar la recursivitat
        if obj.route_position:
            return {
                'id': obj.route_position.id,
                'token': obj.route_position.token,
                'position': obj.route_position.position,
                'zone': obj.route_position.zone,
                'notebook': obj.route_position.notebook,
                'route': obj.route_position.route
            }
        return None
    def get_supply_points(self, obj):
        from .supply_point_serializer import SupplyPointListSerializer  # Local import to avoid circular import
        supply_points = obj.supply_points.all()
        return SupplyPointListSerializer(supply_points, many=True).data

class PropertyListSerializer(serializers.ModelSerializer):
    city = serializers.CharField(source='address_city.name', read_only=True)
    route_position_token = serializers.CharField(source='route_position.token', read_only=True)
    total_supply_points = serializers.SerializerMethodField()
    route = serializers.SerializerMethodField()
    route_position = serializers.IntegerField(source='route_position.position', read_only=True)
    
    class Meta:
        model = Property
        fields = [
            'id',
            'token',
            'name',
            'created_at',
            'city',
            'cadastral',
            'route_position_token',
            'total_supply_points',
            'route',
            'route_position'
        ]
    def get_total_supply_points(self, obj):
        return obj.supply_points.count()
    def get_route(self, obj):
        if obj.route_position and obj.route_position.route:
            return {
                'id': obj.route_position.route.id,
                'name': obj.route_position.route.name,
                'token': obj.route_position.route.token
            }
        return None
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['address'] = str(instance.address_street) + ' ' + str(instance.address_street_number)
        return representation
