from rest_framework import serializers
from django.db.models import Count
from django_filters import rest_framework as filters
from django.utils.translation import gettext as _
from auth.serializers import UserMinimalSerializer
from billing.models import Reading
from coredata.models import City, ConfigProject, PostalCode, Street, StreetNumber, StreetNumberType, StreetType
from coredata.serializers import CityMinimalSerializer, StreetSerializer, StreetNumberSerializer, PostalCodeSerializer, CitySerializer
from service.serializers.supply_point_serializer import SupplyPointSerializer
from ..models import ( Meter, MeterCaliber, MeterLog, MeterStatus, SupplyPoint )
from .value_objects_serializer import MeterStatusSerializer, MeterCaliberSerializer


# Dummy translation list to let makemessages extract the strings
DUMMY_METER_LOG_TRANSLATIONS = [
    # Operations
    _("update"),
    _("create"),
    _("delete"),
    # Fields
    _("status_name"),
    _("caliber_name"),
    _("code"),
    _("is_compound"),
    _("is_property"),
    _("is_general"),
    _("manufacturer"),
    _("manufacturing_year"),
    _("model"),
    _("comm_module"),
    _("comm_module_type"),
    _("comm_technology"),
    _("network_provider"),
    _("installation_at"),
    _("uninstallation_at"),
    _("digits"),
    _("address_street"),
    _("address_street_number"),
    _("address_postal_code"),
    _("address_city"),
    _("latitude"),
    _("longitude"),
    _("is_active"),
    _("meter_general"),
    _("has_remote_reading"),
    # Values
    _("True"),
    _("False"),
]


class MeterLogSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(read_only=True)
    class Meta:
        model = MeterLog
        fields = '__all__'

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        
        user_data = None
        if instance.user:
            user_data = {
                "username": instance.user.username
            }
        
        op_token = instance.operation_token
        if instance.field_name:
            op_token = "update"
        elif not op_token:
            op_token = "update"
            
        field_name = instance.field_name
        old_value = instance.old_value
        new_value = instance.new_value
        
        if field_name == 'status':
            field_name = 'status_name'
            try:
                if old_value and old_value.isdigit():
                    status_obj = MeterStatus.objects.get(id=int(old_value))
                    old_value = status_obj.name
            except Exception:
                pass
            try:
                if new_value and new_value.isdigit():
                    status_obj = MeterStatus.objects.get(id=int(new_value))
                    new_value = status_obj.name
            except Exception:
                pass
        elif field_name == 'caliber':
            field_name = 'caliber_name'
            try:
                if old_value and old_value.isdigit():
                    caliber_obj = MeterCaliber.objects.get(id=int(old_value))
                    old_value = caliber_obj.name
            except Exception:
                pass
            try:
                if new_value and new_value.isdigit():
                    caliber_obj = MeterCaliber.objects.get(id=int(new_value))
                    new_value = caliber_obj.name
            except Exception:
                pass
                
        # Translate values for the frontend
        translated_op_token = _(op_token) if op_token else op_token
        translated_field_name = _(field_name) if field_name else field_name
        translated_old_value = _(old_value) if old_value else old_value
        translated_new_value = _(new_value) if new_value else new_value

        return {
            "operation_token": translated_op_token,
            "created_at": rep.get("created_at"),
            "field_name": translated_field_name,
            "old_value": translated_old_value,
            "new_value": translated_new_value,
            "user": user_data
        }

class MeterSerializer(serializers.ModelSerializer):
    status = serializers.IntegerField(write_only=True)
    supply_point = serializers.SerializerMethodField()
    caliber = serializers.IntegerField(write_only=True)
    address_street = StreetSerializer(required=False, allow_null=True)
    address_street_number = StreetNumberSerializer(required=False, allow_null=True)
    address_postal_code = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    address_city = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    supply_points = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True
    )
    sub_meters = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True
    )
    meter_general = serializers.SerializerMethodField()
    last_reading = serializers.SerializerMethodField()
    # supply_points = serializers.SerializerMethodField()

    def validate_code(self, value):
        query = Meter.objects.filter(code=value, is_active=True)
        if self.instance:
            query = query.exclude(id=self.instance.id)
        if value and query.exists():
            raise serializers.ValidationError("Aquest codi de comptador ja existeix.")
        return value

    class Meta:
        model = Meter
        fields = '__all__'

    def get_last_reading(self, obj):
        reading = Reading.objects.filter(meter=obj, is_control=False, is_initial=False).order_by('-reading_date').first()
        return {
            'id': reading.id,
            'reading_date': reading.reading_date,
            'reading_value': reading.reading_value,
            'leak_value': reading.leak_value,
            'calculated_value': reading.calculated_value,
            'alert': reading.alert.name if reading.alert else None,
            'alert_notes': reading.alert_notes,
        } if reading else None
    
    def validate_caliber(self, value):
        caliber, _ = MeterCaliber.objects.get_or_create(id=value)
        return caliber
    def validate_status(self, value):
        status, _ = MeterStatus.objects.get_or_create(id=value)
        return status
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
        print("CREATING")
        print(validated_data)
        sub_meters_data = validated_data.pop('sub_meters', [])
        supply_points_data = validated_data.pop('supply_points', [])
        street_data = validated_data.pop('address_street', None)
        street_number_data = validated_data.pop('address_street_number', None)

        if street_data:
            type_abbreviation = street_data.pop('type_abbreviation', None)
            type_name = street_data.pop('type_name', '')

        street_type, _ = StreetType.objects.get_or_create(
            abbreviation=type_abbreviation,
            defaults={'name': type_name}
        )

        if street_data.get('street_id'):
            street = Street.objects.get(id=street_data.get('street_id'))
            street.type = street_type
            street.name = street_data['name']
            street.save()
        else:
            street, _ = Street.objects.get_or_create(
                type=street_type,
                name=street_data['name'],
                city=validated_data.get('address_city')
            )
        street_number_type_data = street_number_data.pop('type', None) if street_number_data else None
        if street_number_type_data is None and street_number_data:
            street_number_type_data = street_number_data.pop('number_type', None)

        number_type_type_data = None
        if isinstance(street_number_type_data, dict):
            number_type_type_data = street_number_type_data.get('type')
        if not number_type_type_data and street_number_data:
            number_type_type_data = street_number_data.pop('number_type_type', None)

        if not number_type_type_data:
            number_type_type_data = ConfigProject.objects.get(token='address_street_no_number_type_token').value

        street_number_type, _ = StreetNumberType.objects.get_or_create(
            type=number_type_type_data
        )

        if street_number_data and 'street_number_id' in street_number_data and street_number_data.get('street_number_id'):
            street_number = StreetNumber.objects.get(id=street_number_data.get('street_number_id'))
            street_number.street = street
            street_number.number_type = street_number_type
            street_number.number = street_number_data.get('number', None)
            street_number.number_end = street_number_data.get('number_end', None)
            street_number.number_suffix = street_number_data.get('number_suffix', None)
            street_number.number_end_suffix = street_number_data.get('number_end_suffix', None)
            street_number.save()
        else:
            street_number = StreetNumber.objects.create(
                street=street,
                number_type=street_number_type,
                number = street_number_data.get('number', None) if street_number_data and 'number' in street_number_data else None,
                number_end = street_number_data.get('number_end', None) if street_number_data and 'number_end' in street_number_data else None,
                number_suffix = street_number_data.get('number_suffix', None) if street_number_data and 'number_suffix' in street_number_data else None,
                number_end_suffix = street_number_data.get('number_end_suffix', None) if street_number_data and 'number_end_suffix' in street_number_data else None,
            )

        meter = Meter.objects.create(
            address_street=street,
            address_street_number=street_number,
            **validated_data
        )
        for supply_point_id in supply_points_data:
            supply_point = SupplyPoint.objects.get(id=supply_point_id)
            if supply_point.meter:
                meter.sub_meters.add(supply_point.meter)
            else:
                supply_point.meter = meter
                supply_point.save()

        for meter_id in sub_meters_data:
            sub_meter = Meter.objects.get(id = meter_id)
            if sub_meter:
                meter.sub_meters.add(sub_meter)
        if meter.has_remote_reading:
            meter.has_ever_been_remote = True

        meter.save()

        return meter
    
    def update(self, instance, validated_data):
        street_data = validated_data.pop('address_street', None)
        street_number_data = validated_data.pop('address_street_number', None)
        street = None

        if street_data:
            type_abbreviation = street_data.pop('type_abbreviation')
            type_name = street_data.pop('type_name', '')
            street_type, _ = StreetType.objects.get_or_create(
                abbreviation=type_abbreviation,
                defaults={'name': type_name}
            )


            if street_data.get('street_id'):
                street = Street.objects.get(id=street_data.get('street_id'))
                street.save()
            else:
                street, _ = Street.objects.get_or_create(
                    type=street_type,
                    name=street_data['name'],
                    city=validated_data.get('address_city')
                )
            instance.address_street = street
        else:
            # Needed if only street number is updated
            street = instance.address_street

        if street_number_data:
            
            street_number_type_data = street_number_data.pop('type', None)
            if street_number_type_data is None:
                street_number_type_data = street_number_data.pop('number_type', None)

            number_type_type_data = None
            if isinstance(street_number_type_data, dict):
                number_type_type_data = street_number_type_data.get('type')
            if not number_type_type_data:
                number_type_type_data = street_number_data.pop('number_type_type', None)

            # If there is no number info at all, default to "S/N" (StreetNumberType = SN)
            if not number_type_type_data:
                def _norm_empty(v):
                    return None if v == "" else v

                number = _norm_empty(street_number_data.get('number', None))
                number_end = _norm_empty(street_number_data.get('number_end', None))
                number_suffix = _norm_empty(street_number_data.get('number_suffix', None))
                number_end_suffix = _norm_empty(street_number_data.get('number_end_suffix', None))
                if number is None and number_end is None and number_suffix is None and number_end_suffix is None:
                    number_type_type_data = "SN"

            if not number_type_type_data:
                raise serializers.ValidationError(
                    {"address_street_number": "Falta el tipus de número (`number_type.type` / `number_type_type`)."}
                )

            street_number_type, _ = StreetNumberType.objects.get_or_create(type=number_type_type_data)

            if street_number_data and 'street_number_id' in street_number_data and street_number_data.get('street_number_id'):
                street_number = StreetNumber.objects.get(id=street_number_data.get('street_number_id'))
                if street:
                    street_number.street = street
                street_number.number_type = street_number_type
                # Only touch number fields explicitly present in the payload: this row can be
                # shared with other entities (e.g. a SupplyPoint's Address), so a key that is
                # simply absent from a partial update must not be treated as "clear it".
                if 'number' in street_number_data:
                    street_number.number = street_number_data.get('number')
                if 'number_end' in street_number_data:
                    street_number.number_end = street_number_data.get('number_end')
                if 'number_suffix' in street_number_data:
                    street_number.number_suffix = street_number_data.get('number_suffix')
                if 'number_end_suffix' in street_number_data:
                    street_number.number_end_suffix = street_number_data.get('number_end_suffix')
                street_number.save()
            else:
                if not street:
                    raise serializers.ValidationError(
                        {"address_street": "Es requereix `address_street` per crear un nou número de carrer."}
                    )
                street_number = StreetNumber.objects.create(
                    street=street,
                    number_type=street_number_type,
                    number = street_number_data.get('number', None) if street_number_data and 'number' in street_number_data else None,
                    number_end = street_number_data.get('number_end', None) if street_number_data and 'number_end' in street_number_data else None,
                    number_suffix = street_number_data.get('number_suffix', None) if street_number_data and 'number_suffix' in street_number_data else None,
                    number_end_suffix = street_number_data.get('number_end_suffix', None) if street_number_data and 'number_end_suffix' in street_number_data else None,
                )
            instance.address_street_number = street_number

        supply_points_data = validated_data.pop('supply_points', [])
        supply_points_list = []

        for supply_point_id in supply_points_data:
            supply_point = SupplyPoint.objects.get(id=supply_point_id)
            if supply_point:
                supply_points_list.append(supply_point)

        instance.supply_points.set(supply_points_list)

        sub_meters_data = validated_data.pop('sub_meters', [])
        sub_meters_list = []

        for sub_meter_id in sub_meters_data:
            sub_meter = Meter.objects.get(id=sub_meter_id)
            if sub_meter:
                sub_meters_list.append(sub_meter)

        instance.sub_meters.set(sub_meters_list)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if instance.has_remote_reading:
            instance.has_ever_been_remote = True

        instance.save()
        return instance
    
    def get_meter_general(self, obj):
        if obj.meter_general:
            return MeterListSerializer(obj.meter_general).data
        return None
    
    def get_supply_point(self, obj):
        # Inclou només els camps essencials per trencar la recursivitat
        direct_supply_points = obj.supply_points.all()
        if direct_supply_points and direct_supply_points[0]:
            return {
                "id": direct_supply_points[0].id,
                "name": direct_supply_points[0].name,
                "token": direct_supply_points[0].token,
                "address": str(direct_supply_points[0].address) if direct_supply_points[0].address else None
            }
        return None
    
    def get_supply_points(self, obj):
        direct_supply_points = obj.supply_points.all()
        response = []
        for supply_point in direct_supply_points:
            response.append({
                "id": supply_point.id,
                "name": supply_point.name,
                "token": supply_point.token,
                "address_complete": str(supply_point.address) if supply_point.address else None,
                "meter": supply_point.meter.code if supply_point.meter else None,
                "meter_id": supply_point.meter.id,
                "status_name": supply_point.status.name if supply_point.status else None,
                "status_color": supply_point.status.color if supply_point.status else None,
            })
        return response
    
    def _sub_meter_supply_point(self, meter):
        """Supply point del sub_meter (el primero si tiene varios) para incluir en la respuesta."""
        sp = meter.supply_points.first()
        if not sp:
            return None
        return {
            "id": sp.id,
            "token": sp.token,
            "address_complete": str(sp.address) if sp.address else None,
        }

    def get_filtered_sub_meters(self, obj):
        sub_meters = obj.sub_meters.all()
        sub_meters_list = []
        for meter in sub_meters:
            sub_meters_list.append({
                "id": meter.id,
                "code": meter.code,
                "status": MeterStatusSerializer(meter.status).data if meter.status else None,
                "address_street": StreetSerializer(meter.address_street).data if meter.address_street else None,
                "address_street_number": StreetNumberSerializer(meter.address_street_number).data if meter.address_street_number else None,
                "address_postal_code": PostalCodeSerializer(meter.address_postal_code).data if meter.address_postal_code else None,
                "address_city": CityMinimalSerializer(meter.address_city).data if meter.address_city else None,
                "supply_point": self._sub_meter_supply_point(meter),
            })
        return sub_meters_list
    
    def is_detail_view(self):
        view = self.context.get('view')
        request = self.context.get('request')
        if view and request:
            # Check if 'lookup_url_kwarg' or 'lookup_field' is in view's kwargs
            if hasattr(view, 'kwargs') and view.kwargs.get(view.lookup_url_kwarg or view.lookup_field):
                return True
        return False

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['address_complete'] = str(instance)
        representation['street_complete'] = str(instance.address_street)
        representation['name'] = str(instance)

        representation['address_postal_code'] = PostalCodeSerializer(instance.address_postal_code).data if instance.address_postal_code else None
        representation['address_city'] = CitySerializer(instance.address_city).data if instance.address_city else None
        
        representation['caliber'] = MeterCaliberSerializer(instance.caliber).data
        representation['status'] = MeterStatusSerializer(instance.status).data
        
        # representation['is_telecontrol'] = True if instance.comm_module is not None and instance.comm_module_type is not None else False
        representation['is_telecontrol'] = False
        

        if self.is_detail_view():
            representation['supply_points'] = self.get_supply_points(instance)
            representation['sub_meters'] = self.get_filtered_sub_meters(instance)
        return representation
    

class MeterReadingDocumentSerializer(serializers.ModelSerializer):
    supply_points = serializers.SerializerMethodField()
    readings = serializers.SerializerMethodField()
    class Meta:
        model = Meter
        fields = '__all__'
    
    def get_supply_points(self, instance):
        return [{'id': supply_point.id, 'token': supply_point.token} for supply_point in instance.supply_points.all()]
    
    def get_readings(self, instance):
        readings = Reading.objects.filter(id__in=getattr(instance, 'reading_ids', []))
        
        return [ {
                'id': reading.id,
                'reading_date': reading.reading_date,
                'reading_value': reading.reading_value,
                'calculated_value': reading.calculated_value,
                'leak_value': reading.leak_value,
                'real_consumption': reading.real_consumption,
                'is_control': reading.is_control,
                'is_estimated': reading.is_estimated,
                'origin': reading.origin,
                'estimated_used': reading.estimated_used,
                'alert': reading.alert.name if reading.alert else None,
                'remote_alert': reading.remote_alert.name if reading.remote_alert else None,
                } for reading in readings]

class MeterListSerializer(serializers.ModelSerializer):
    status_token = serializers.CharField(source='status.token', read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    caliber_token = serializers.CharField(source='caliber.token', read_only=True)
    caliber_name = serializers.CharField(source='caliber.name', read_only=True)
    
    last_reading_id = serializers.SerializerMethodField()
    
    class Meta:
        model = Meter
        fields = [
            'id',
            'code',
            'created_at',
            'installation_at',
            'uninstallation_at',
            'status_token',
            'status_name',
            'status_color',
            'is_general',
            'has_remote_reading',
            'last_reading_id',
            'manufacturer',
            'manufacturing_year',
            'comm_technology',
            'caliber_token',
            'caliber_name',
        ]
    
    def get_last_reading_id(self, obj):
        by_meter = self.context.get('last_reading_id_by_meter')
        if by_meter is not None:
            return by_meter.get(obj.id)
        try:
            reading = Reading.objects.filter(meter=obj, is_active=True).order_by("-reading_date").first()
            return reading.id if reading else None
        except Exception:
            return None
        
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['address_street'] = str(instance.address_street) if instance.address_street_id else None
        representation['address_city'] = str(instance.address_city) if instance.address_city_id else None

        supply_points = list(instance.supply_points.all())
        supply_point = supply_points[0] if supply_points else None
        if supply_point:
            exploitation = (
                supply_point.connection.exploitation
                if supply_point.connection_id and supply_point.connection and supply_point.connection.exploitation_id
                else None
            )
            representation['exploitation_name'] = str(exploitation.name) if exploitation else None
            representation['supply_point_status'] = (
                str(supply_point.status.name) if supply_point.status_id and supply_point.status else None
            )
            representation['supply_point_status_color'] = (
                str(supply_point.status.color) if supply_point.status_id and supply_point.status else None
            )
            representation['supply_point_status_token'] = (
                str(supply_point.status.token) if supply_point.status_id and supply_point.status else None
            )
            representation['supply_point'] = str(supply_point.address) if supply_point.address_id else None
        else:
            representation['exploitation_name'] = None
            representation['supply_point_status'] = None
            representation['supply_point_status_color'] = None
            representation['supply_point_status_token'] = None
            representation['supply_point'] = None

        by_meter = self.context.get('last_reading_by_meter')
        if by_meter is not None:
            reading = by_meter.get(instance.id)
            if reading:
                representation['last_reading'] = {
                    'id': reading.id,
                    'reading_date': reading.reading_date,
                    'reading_value': reading.reading_value,
                    'consumption_days': reading.consumption_days,
                    'is_estimated': reading.is_estimated,
                    'contract_request_id': reading.contract_request_id,
                    'is_initial': reading.is_initial,
                    'alert': reading.alert.name if reading.alert_id and reading.alert else None,
                    'alert_notes': reading.alert_notes,
                }
            else:
                representation['last_reading'] = None
        else:
            try:
                reading = Reading.objects.filter(
                    meter=instance, is_close=False, is_control=False
                ).select_related('alert').order_by('-reading_date').first()
                if reading:
                    representation['last_reading'] = {
                        'id': reading.id,
                        'reading_date': reading.reading_date,
                        'reading_value': reading.reading_value,
                        'consumption_days': reading.consumption_days,
                        'is_estimated': reading.is_estimated,
                        'contract_request_id': reading.contract_request_id,
                        'is_initial': reading.is_initial,
                        'alert': reading.alert.name if reading.alert else None,
                        'alert_notes': reading.alert_notes,
                    }
                else:
                    representation['last_reading'] = None
            except Exception:
                representation['last_reading'] = None

        return representation





class MeterMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meter
        fields = ['id', 'code', 'is_active', 'has_remote_reading']