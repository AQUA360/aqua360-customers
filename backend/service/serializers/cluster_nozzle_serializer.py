from rest_framework import serializers
from django_filters import rest_framework as filters

from coredata.models import Address, City, Province, Street, StreetNumber, StreetType, StreetNumberType, Country
from coredata.utils.name_utils import generate_token
from service.serializers.supply_point_serializer import SupplyPointSaveNozzleSerializer, SupplyPointSerializer
from ..models import ( ClusterNozzle, Cluster, SupplyPoint, SupplyPointPlacement, SupplyPointStatus )
from .value_objects_serializer import ClusterNozzleStatusSerializer, ClusterNozzleTypeSerializer


class ClusterNozzleSerializer(serializers.ModelSerializer):
    supply_points = serializers.SerializerMethodField()
    status = ClusterNozzleStatusSerializer(required=False, allow_null=True)
    type = ClusterNozzleTypeSerializer(required=False, allow_null=True)
    cluster = serializers.SerializerMethodField()

    class Meta:
        model = ClusterNozzle
        fields = '__all__'

    def get_supply_points(self, obj):
        return [
            {
                "id": sp.id,
                "token": sp.token,
                "type": sp.type.id if sp.type else None,
                "supply_type": sp.supply_type.id if sp.supply_type else None,
                "source": sp.source.id if sp.source else None,
                "placement": sp.placement.id if sp.placement else None,
                "status_token": sp.status.token if sp.status else None,
                "status_name": sp.status.name if sp.status else None,
                "status_color": sp.status.color if sp.status else None,
                "meter_id": sp.meter.id if sp.meter else None,
                "meter_code": sp.meter.code if sp.meter else None,
                "address": {
                    "building": sp.address.building if sp.address else None,
                    "floor": sp.address.floor if sp.address else None,
                    "door": sp.address.door if sp.address else None,
                    "stair": sp.address.stair if sp.address else None,
                }
            }
            for sp in obj.supply_points.all()
        ]

    def get_cluster(self, obj):
        if obj.cluster:
            return {
                "id": obj.cluster.id,
                "token": obj.cluster.token
            }
        return None

class ClusterNozzleSaveSerializer(serializers.ModelSerializer):
    token = serializers.CharField(required=False, allow_blank=True)
    cluster = serializers.PrimaryKeyRelatedField(queryset=Cluster.objects.all(), required=False, allow_null=True)
    supplyPoint = SupplyPointSaveNozzleSerializer(write_only=True, required=False, allow_null=True)
    supply_point_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    # Accept any input for diameter and coerce manually to int/None
    diameter = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    class Meta:
        model = ClusterNozzle
        fields = '__all__'

    def get_supply_points(self, obj):
        return [
            {"id": sp.id, "token": sp.token}
            for sp in obj.supply_points.all()
        ]

    def get_cluster(self, obj):
        if obj.cluster:
            return {
                "id": obj.cluster.id,
                "token": obj.cluster.token
            }
        return None
    def validate(self, data):
        if not self.instance and 'token' not in data:
            raise serializers.ValidationError({"token": "This field is required."})
        
        return data

    def validate_diameter(self, value):
        if value in [None, '']:
            return None
        try:
            # Accept numeric strings like "25" or "25.0" by int(float())
            if isinstance(value, (int, float)):
                return int(value)
            return int(float(str(value).strip()))
        except (ValueError, TypeError):
            return None

    
    def create(self, validated_data):
        supply_data = None
        if 'supplyPoint' in validated_data:
            supply_data = validated_data.pop('supplyPoint')
        supply_point_id = validated_data.pop('supply_point_id', None)

        cluster_nozzle = ClusterNozzle.objects.create(
            **validated_data
        )
        if supply_point_id:
            cluster_nozzle.supply_points.exclude(id=supply_point_id).update(cluster_nozzle=None)
            supply_point = SupplyPoint.objects.get(id=supply_point_id)
            supply_point.cluster_nozzle = cluster_nozzle
            supply_point.save()
        if supply_data:
            print("supply_data", supply_data)
            # Let SupplyPointSaveNozzleSerializer handle address creation
                
            status = SupplyPointStatus.objects.get(is_default=True)
                
            # Use the SupplyPointSaveNozzleSerializer to create the supply point
            supply_serializer = SupplyPointSaveNozzleSerializer(data=supply_data)
            if supply_serializer.is_valid():
                supply_point = supply_serializer.save(
                    status=status,
                    cluster_nozzle=cluster_nozzle,
                    connection=cluster_nozzle.cluster.connection,
                    property=cluster_nozzle.cluster.property
                )
            else:
                raise Exception(f"SupplyPoint validation failed: {supply_serializer.errors}")
            
            supply_point.token = generate_token(SupplyPoint) if not supply_point.token else supply_point.token
            supply_point.property = cluster_nozzle.cluster.property
            supply_point.save()
        
        return cluster_nozzle
    


    def update(self, instance, validated_data):
        supply_point_id = None
        supply_data = None
        if 'supplyPoint' in validated_data:
            supply_data = validated_data.pop('supplyPoint')
            
        if 'supply_point_id' in validated_data:
            supply_point_id = validated_data.pop('supply_point_id')
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if supply_point_id and not supply_data:
            instance.supply_points.exclude(id=supply_point_id).update(cluster_nozzle=None)
            supply_point = SupplyPoint.objects.get(id = supply_point_id)
            supply_point.cluster_nozzle = instance
            supply_point.save()
        elif supply_data:
            address = None
            if 'address' in supply_data:
                address_data = supply_data.pop('address')
                address = self._create_address_from_data(address_data)

            if supply_point_id:
                instance.supply_points.exclude(id=supply_point_id).update(cluster_nozzle=None)
                supply_point = SupplyPoint.objects.get(id = supply_point_id)
                for attr, value in supply_data.items():
                    setattr(supply_point, attr, value)
                supply_point.cluster_nozzle = instance
                if address:
                    supply_point.address = address
                supply_point.save()
            else:
                status = SupplyPointStatus.objects.get(is_default=True)
                new_supply_point = SupplyPoint.objects.create(
                    **supply_data,
                    status = status,
                    address = address,
                    cluster_nozzle = instance,
                    connection = instance.cluster.connection,
                    property = instance.cluster.property,
                )
                new_supply_point.token = str(new_supply_point.id).zfill(6)
                new_supply_point.save()
        return instance
    
    def _create_address_from_data(self, address_data):
        """Create Address from the nested data structure"""
        street_data = address_data.get('street', {})
        street_number_data = address_data.get('street_number', {})
        
        # Handle city, province, country
        city = None
        if address_data.get('city'):
            try:
                city = City.objects.get(id=address_data['city'])
            except City.DoesNotExist:
                raise serializers.ValidationError(f"City with id {address_data['city']} not found")
        
        province = None
        if address_data.get('province'):
            try:
                province = Province.objects.get(id=address_data['province'])
            except Province.DoesNotExist:
                raise serializers.ValidationError(f"Province with id {address_data['province']} not found")
        
        country = None
        if address_data.get('country'):
            try:
                country = Country.objects.get(id=address_data['country'])
            except Country.DoesNotExist:
                raise serializers.ValidationError(f"Country with id {address_data['country']} not found")

        # Handle street
        street = None
        if street_data:
            street_type_data = street_data.get('type', {})
            if isinstance(street_type_data, dict):
                # Create or get StreetType
                street_type, _ = StreetType.objects.get_or_create(
                    abbreviation=street_type_data.get('abbreviation', ''),
                    defaults={'name': street_type_data.get('name', '')}
                )
            else:
                street_type = street_type_data
            
            # Create or get Street
            if street_data.get('street_id'):
                street = Street.objects.get(id=street_data['street_id'])
                street.type = street_type
                street.name = street_data.get('name', street.name)
                street.city = city
                street.save()
            else:
                street, _ = Street.objects.get_or_create(
                    name=street_data.get('name', ''),
                    city=city,
                    defaults={'type': street_type}
                )
        
        # Handle street number
        street_number = None
        if street_number_data:
            number_type_data = street_number_data.get('number_type', {})
            if isinstance(number_type_data, dict):
                # Create or get StreetNumberType
                street_number_type, _ = StreetNumberType.objects.get_or_create(
                    type=number_type_data.get('type', 'N'),
                    defaults={'description': number_type_data.get('description', '')}
                )
            else:
                street_number_type = number_type_data
            
            # Create or get StreetNumber
            if street_number_data.get('street_number_id'):
                street_number = StreetNumber.objects.get(id=street_number_data['street_number_id'])
                street_number.street = street
                street_number.number_type = street_number_type
                street_number.number = street_number_data.get('number', street_number.number)
                street_number.save()
            else:
                street_number, _ = StreetNumber.objects.get_or_create(
                    street=street,
                    number_type=street_number_type,
                    number=street_number_data.get('number', ''),
                    defaults={
                        'number_end': street_number_data.get('number_end'),
                        'number_suffix': street_number_data.get('number_suffix', ''),
                        'number_end_suffix': street_number_data.get('number_end_suffix')
                    }
                )

        # Create Address
        
        if Address.objects.filter(street=street,
            street_number=street_number,
            city=city,
            province=province,
            country=country,
            postal_code=address_data.get('postal_code', ''),
            building=address_data.get('building', ''),
            floor=address_data.get('floor', ''),
            door=address_data.get('door', ''),
            stair=address_data.get('stair', '')).exists():
            
            address = Address.objects.filter(street=street,
                street_number=street_number,
                city=city,
                province=province,
                country=country,
                postal_code=address_data.get('postal_code', ''),
                building=address_data.get('building', ''),
                floor=address_data.get('floor', ''),
                door=address_data.get('door', ''),
                stair=address_data.get('stair', '')).first()
        else:
            address = Address.objects.create(
                street=street,
                street_number=street_number,
                city=city,
                province=province,
                country=country,
                postal_code=address_data.get('postal_code', ''),
                building=address_data.get('building', ''),
                floor=address_data.get('floor', ''),
                door=address_data.get('door', ''),
                stair=address_data.get('stair', '')
            )
        
        return address