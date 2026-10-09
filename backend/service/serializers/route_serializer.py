from rest_framework import serializers
from django_filters import rest_framework as filters
from coredata.serializers import CitySerializer, PostalCodeSerializer, StreetNumberSerializer, StreetSerializer
from service.utils.route_positions_service import route_count_total_readings, route_position_change, regenerate_route_position_token
from service.utils.property_route_service import sync_property_tokens_with_route_position
from ..models import ( Property, RouteZone, RoutePosition, Route, SupplyPoint )
from django.db.models import Count, Sum


def _serialize_properties(route_position):
    """Retorna una llista lleugera de propietats amb adreça i supply points."""
    result = []
    for prop in route_position.properties.all():
        supply_points = [
            {
                'id': sp.id,
                'token': sp.token,
                'name': sp.name,
            }
            for sp in prop.supply_points.all()
        ]
        result.append({
            'id': prop.id,
            'token': prop.token,
            'name': prop.name,
            'address_street': StreetSerializer(prop.address_street).data if prop.address_street else None,
            'address_street_number': StreetNumberSerializer(prop.address_street_number).data if prop.address_street_number else None,
            'address_city': CitySerializer(prop.address_city).data if prop.address_city else None,
            'address_postal_code': PostalCodeSerializer(prop.address_postal_code).data if prop.address_postal_code else None,
            'supply_points': supply_points,
        })
    return result


class RouteZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = RouteZone
        fields = '__all__'

class RoutePositionListSerializer(serializers.ModelSerializer):
    # read
    properties = serializers.SerializerMethodField()
    
    # write
    property_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_null=True)
    route_id = serializers.IntegerField(write_only=True, 
        required=False, 
        allow_null=True)

    class Meta:
        model = RoutePosition
        fields = '__all__'

    def get_properties(self, obj):
        return _serialize_properties(obj)
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['name'] = instance.name

        route = instance.route

        if route:
            representation['route'] = {
                'id': route.id,
                'name': route.name,
                'token': route.token
            }
            if route.route_zone:
                representation['route']['route_zone'] = {
                    'id': route.route_zone.id,
                    'name': route.route_zone.name,
                    'token': route.route_zone.token
                }
        
        return representation

class RoutePositionSerializer(serializers.ModelSerializer):
    # read
    properties = serializers.SerializerMethodField()
    
    # write
    property_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_null=True
    )
    route_id = serializers.IntegerField(write_only=True, 
        required=False, 
        allow_null=True)
    supply_points_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False, 
        allow_null=True
    )
    position_num = serializers.IntegerField(write_only=True, 
        required=False, 
        allow_null=True)
    
    class Meta:
        model = RoutePosition
        fields = '__all__'

    def get_properties(self, obj):
        return _serialize_properties(obj)

    def create(self, validated_data):
        supply_points_ids = validated_data.pop('supply_points_ids', None)
        property_ids = validated_data.pop('property_ids', None)
        route_id = validated_data.pop('route_id', None)

        route_position = RoutePosition.objects.create(**validated_data)

        if route_id and route_id != 0:
            route = Route.objects.get(id=route_id)
            if route:
                route.positions.add(route_position)
                route.save()

        if property_ids:
            for property_id in property_ids:
                prop = Property.objects.filter(id=property_id).first()
                if prop:
                    prop.route_position = route_position
                    prop.save()

                    if supply_points_ids:
                        for supply_id in supply_points_ids:
                            supply_point = SupplyPoint.objects.filter(id=supply_id).first()
                            if supply_point:
                                supply_point.property = prop
                                supply_point.save()

            sync_property_tokens_with_route_position(route_position)

        return route_position
    
    def update(self, instance, validated_data):
        supply_points_ids = validated_data.pop('supply_points_ids', None)
        property_ids = validated_data.pop('property_ids', None)
        
        # Acceptem tant 'position' (enviat pel front normalment) com 'position_num' per trigger de canvi
        new_position = validated_data.pop('position_num', None)
        if new_position is None:
            new_position = validated_data.get('position', None)
        
        route_id = validated_data.pop('route_id', None)
        
        # Eliminem 'id' de validated_data si hi és, ja que és un camp del model en Meta.fields
        validated_data.pop('id', None)
        
        old_position = instance.position
        old_route_id = instance.route.id if instance.route else None

        # Actualitzem camps directes
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if route_id:
            route = Route.objects.filter(id=route_id).first()
            if route:
                instance.route = route
        
        # Si la posició ha canviat o se'ns demana explícitament (new_position)
        # Executem la lògica de reordenació si tenim ruta
        position_changed = new_position is not None and (new_position != old_position or route_id != old_route_id)
        if position_changed:
            instance.position = new_position
            if instance.route:
                route_position_change(instance.route.id, new_position, exclude_id=instance.id)

        instance.save()

        if position_changed:
            regenerate_route_position_token(instance)

        if property_ids is not None:
            # 1. Desvinculem aquelles que ja no estan a la llista per aquesta RoutePosition
            instance.properties.exclude(id__in=property_ids).update(route_position=None)
            
            # 2. Vinculem les que sí que hi són
            for property_id in property_ids:
                prop = Property.objects.filter(id=property_id).first()
                if prop:
                    prop.route_position = instance
                    prop.save()

                    if supply_points_ids is not None:
                        # 3. Desvinculem punts de subministrament que ja no estiguin a la llista per aquesta finca
                        prop.supply_points.exclude(id__in=supply_points_ids).update(property=None)
                        
                        # 4. Vinculem els que sí que hi són
                        for supply_id in supply_points_ids:
                            supply_point = SupplyPoint.objects.filter(id=supply_id).first()
                            if supply_point:
                                supply_point.property = prop
                                supply_point.save()

        sync_property_tokens_with_route_position(instance)

        return instance
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['name'] = instance.name

        route = instance.route

        if route:
            representation['route'] = {
                'id': route.id,
                'name': route.name,
                'token': route.token
            }
            if route.route_zone:
                representation['route']['route_zone'] = {
                    'id': route.route_zone.id,
                    'name': route.route_zone.name,
                    'token': route.route_zone.token
                }
                
        representation['address_street'] = StreetSerializer(instance.address_street).data if instance.address_street else None
        representation['address_street_number'] = StreetNumberSerializer(instance.address_street_number).data if instance.address_street_number else None
        representation['address_city'] = CitySerializer(instance.address_city).data if instance.address_city else None
        representation['address_postal_code'] = PostalCodeSerializer(instance.address_postal_code).data if instance.address_postal_code else None
        
        return representation
    
class RoutePositionAppSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoutePosition
        fields = '__all__'

class PositionUpdateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    position = serializers.IntegerField()

class RouteSerializer(serializers.ModelSerializer):
    route_zone = RouteZoneSerializer(required=False, allow_null=True)
    route_zone_id = serializers.IntegerField(required=False, allow_null=True)
    
    position_ids_to_add = serializers.ListField(
        child=PositionUpdateSerializer(),
        write_only=True
    )
    position_ids_to_remove = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True
    )
    class Meta:
        model = Route
        fields = '__all__'

    def create(self, validated_data):
        position_ids_to_add = validated_data.pop('position_ids_to_add', None)
        position_ids_to_remove = validated_data.pop('position_ids_to_remove', None)
        route_zone_id = validated_data.pop('route_zone_id', None)

        route = Route.objects.create(**validated_data)
        
        if route_zone_id:
            zone = RouteZone.objects.get(id=route_zone_id)
            route.route_zone = zone

        if position_ids_to_add:
            for position_data in position_ids_to_add:
                position = RoutePosition.objects.get(id=position_data['id'])
                if position:
                    position.position = position_data['position']
                    position.save()
                    route.positions.add(position)
                    
        if position_ids_to_remove:
            for position_id in position_ids_to_remove:
                position = RoutePosition.objects.get(id=position_id)
                if position:
                    route.positions.remove(position)

        route.save()
        return route

    def update(self, instance, validated_data):
        route_zone_id = validated_data.pop('route_zone_id', None)
        position_ids_to_add = validated_data.pop('position_ids_to_add', None)
        position_ids_to_remove = validated_data.pop('position_ids_to_remove', None)
        if route_zone_id:
            zone = RouteZone.objects.get(id=route_zone_id)
            instance.route_zone = zone

        if position_ids_to_add:
            # Ordre descendent per evitar col·lisions de unique_together(route, position):
            # primer desplacem les posicions altes (que no xoquen amb ningú) i
            # després assignem les baixes (que ja estan lliures).
            for position_data in sorted(position_ids_to_add, key=lambda x: x['position'], reverse=True):
                RoutePosition.objects.filter(id=position_data['id']).update(position=position_data['position'])
                rp = RoutePosition.objects.get(id=position_data['id'])
                instance.positions.add(rp)
                    
        if position_ids_to_remove:
            for position_id in position_ids_to_remove:
                position = RoutePosition.objects.get(id=position_id)
                if position:
                    instance.positions.remove(position)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        return representation

class RouteListSerializer(serializers.ModelSerializer):
    zone_name = serializers.CharField(source='route_zone.name', read_only=True)
    num_total_readings = serializers.SerializerMethodField()
    num_telecontrol_readings = serializers.SerializerMethodField()

    class Meta:
        model = Route
        fields = [
            'id',
            'token',
            'created_at',
            'name',
            'zone_name',
            'num_total_readings',
            'num_telecontrol_readings'
        ]

    def get_num_total_readings(self, obj):
        return (
            obj.positions
            .filter(properties__isnull=False)
            .annotate(num_supplypoints=Count('properties__supply_points'))
            .aggregate(total=Sum('num_supplypoints'))['total'] or 0
        )

    def get_num_telecontrol_readings(self, obj):
        return (
            obj.positions
            .filter(properties__isnull=False)
            .filter(properties__supply_points__meter__isnull=False)
            .filter(properties__supply_points__meter__has_remote_reading=True, properties__supply_points__meter__force_manual_reading=False)
            .aggregate(total_telecontrol=Count('properties__supply_points', distinct=True))['total_telecontrol'] or 0
        )
