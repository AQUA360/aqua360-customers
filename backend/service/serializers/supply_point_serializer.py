import base64
from django.utils import timezone
from datetime import timedelta 
from rest_framework import serializers
from django_filters import rest_framework as filters
from django.db.models import Q, Max, Sum
from billing.models import Payment, PaymentStatus, Reading, ReadingBatch, ReadingBatchStatus
from billing.serializers.estimated_bag_serializer import EstimatedBagMinimalSerializer, EstimatedBagSerializer
from billing.serializers.value_objects_serializer import RemoteReadingAlertSerializer
from contract.models import ContractStatus
from coredata.models import Address, City, ConfigProject, Country, PostalCode, Province, Street, StreetNumber, StreetNumberType, StreetType
from coredata.serializers import AddressSerializer
from auth.serializers import UserMinimalSerializer
from coredata.utils.name_utils import generate_token, check_token_exists
from fraud.models import Fraud
from service.utils.supply_point_service import supply_point_change_address, supply_point_change_connection, supply_point_change_meter, supply_point_change_property
from service.utils.supply_cut_service import is_temporary_cause as supply_cut_is_temporary
from service.utils.supply_cut_service import planned_cut_is_stale
from service.utils.property_route_service import auto_assign_route_to_property
from ..models import ( Cluster, ClusterNozzleStatus, ClusterNozzleType, Route, RoutePosition, SupplyPointObservation, SupplyPoint, SupplyPointPlacement, SupplyPointType, SupplyPointStatus, SupplyPointSource, SupplyPointSupplyType, ClusterNozzle, Connection, Meter, Property )
from .value_objects_serializer import SupplyPointPlacementSerializer, SupplyPointTypeSerializer, SupplyPointStatusSerializer, SupplyPointSourceSerializer, SupplyPointSupplyTypeSerializer, MeterStatusSerializer
from .connection_serializer import ConnectionSerializer
# from .cluster_nozzle_serializer import ClusterNozzleSerializer
from .property_serializer import PropertySerializer


def _get_active_contract_status():
    active_contract_token = ConfigProject.objects.get(token='contract_active_token').value
    return ContractStatus.objects.get(token=active_contract_token)


def _supply_cut_alert(supply_point):
    """Alerta de tall vigent per a un PP.
    Es mostra si està Actiu (sempre, independentment de la data).
    Es mostra si està Planificat fins a 30 minuts després de la seva fi prevista.
    """
    cuts = getattr(supply_point, '_prefetched_supply_cuts', None)
    if not cuts:
        return None
        
    now = timezone.now()
    margin_time = now - timedelta(minutes=30)
    
    for cut in cuts:
        if cut.requires_review or cut.status is None or cut.status.token not in ('0', '1'):
            continue
            
        if cut.status.token == '0':
            # Si està Planificat, apliquem el marge de 30 minuts un cop superada la data de fi
            if not cut.date_end or cut.date_end < margin_time:
                continue
                
        # Si està Actiu ('1'), no fem cap comprovació de data. 
        # Es mostrarà ininterrompudament fins que algú el passi a Acabat ('2') o Cancel·lat ('3').
        
        return {
            'id': cut.id,
            'token': cut.token,
            'status_token': cut.status.token,
            'status_name': cut.status.name,
            'temporary': supply_cut_is_temporary(cut),
            'cause_token': cut.cause.token if cut.cause else None,
            'cause_name': cut.cause.name if cut.cause else None,
            'date_end': cut.date_end,
        }
    return None


def _resolve_postal_code(value, city=None):
    if value is None or value == '':
        return None

    queryset = PostalCode.objects.all()
    if city:
        queryset = queryset.filter(cities=city)

    if str(value).isdigit():
        postal_code = queryset.filter(id=int(value)).first()
        if postal_code:
            return postal_code

    return queryset.filter(code=str(value)).first()


class SupplyPointObservationSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = SupplyPointObservation
        fields = '__all__'

class SupplyPointListSerializer(serializers.ModelSerializer):
    type_token = serializers.CharField(source='type.token', read_only=True)
    type_name = serializers.CharField(source='type.name', read_only=True)
    status_token = serializers.CharField(source='status.token', read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    property_route_position_token = serializers.CharField(source='property.route_position.token', read_only=True)
    meter_code = serializers.CharField(source='meter.code', read_only=True)
    cluster_nozzle_token = serializers.CharField(source='cluster_nozzle.token', read_only=True)
    connection_token = serializers.CharField(source='connection.token', read_only=True)
    connection_exploitation_token = serializers.CharField(source='connection.exploitation.token', read_only=True)
    connection_exploitation_name = serializers.CharField(source='connection.exploitation.name', read_only=True)
    placement_name = serializers.CharField(source='placement.name', read_only=True, allow_null=True)
    address_city = serializers.CharField(source='address.city', read_only=True)
    address_country = serializers.CharField(source='address.country', read_only=True)
    street_id = serializers.IntegerField(source='address.street.id', read_only=True)
    address_postal_code = serializers.CharField(source='address.postal_code', read_only=True)
    meter_manufacturer = serializers.CharField(source='meter.manufacturer', read_only=True)
    meter_model = serializers.CharField(source='meter.model', read_only=True)
    supply_point_children_ids = serializers.SerializerMethodField()
    sub_meters = serializers.SerializerMethodField()
    supply_cut_alert = serializers.SerializerMethodField()
    current_fraud = serializers.BooleanField(read_only=True)
    previous_fraud = serializers.BooleanField(read_only=True)
    property_id = serializers.IntegerField(source='property.id', read_only=True)
    property_token = serializers.CharField(source='property.token', read_only=True)
    property_name = serializers.CharField(source='property.name', read_only=True)

    class Meta:
        model = SupplyPoint
        fields = [
            'id',
            'token',
            'address',
            'address_city',
            'street_id',
            'address_country',
            'current_fraud',
            'previous_fraud',
            'type_token',
            'type_name',
            'status_token',
            'status_name',
            'status_color',
            'property_route_position_token',
            'meter_code',
            'meter_id',
            'cluster_nozzle_token',
            'connection_token',     
            'connection_exploitation_token',
            'connection_exploitation_name',
            'placement_name',
            'is_potable',
            'supply_point_children_ids',
            'sub_meters',
            'supply_cut_alert',
            'address_postal_code',
            'meter_manufacturer',
            'meter_model',
            'property_id',
            'property_token',
            'property_name',
        ]
    
    
    def get_supply_point_children_ids(self, obj):
        return [child.id for child in obj.supply_point_children.all()]

    def get_supply_cut_alert(self, obj):
        return _supply_cut_alert(obj)

    def _sub_meter_supply_point(self, meter):
        """Supply point del sub_meter (el primero si tiene varios) para incluir en la respuesta."""
        sp = meter.supply_points.first()
        if not sp:
            return None
        return {"id": sp.id, "token": sp.token, "address_complete": str(sp.address) if sp.address else None}

    def get_sub_meters(self, obj):
        """Sub_meters del contador de este supply point, para mostrarlos anidados en el front."""
        if not obj.meter:
            return []
        sub_meters = obj.meter.sub_meters.all()
        return [
            {
                'id': m.id,
                'code': m.code,
                'status': MeterStatusSerializer(m.status).data if m.status else None,
                'has_remote_reading': getattr(m, 'has_remote_reading', False),
                'supply_point': self._sub_meter_supply_point(m),
            }
            for m in sub_meters
        ]


    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['address_complete'] = str(instance.address)
        
        if instance.meter:
            representation['is_telecontrol'] = instance.meter.has_remote_reading if instance.meter else False
        
        contracts = []
        # Get active contracts from prefetched data
        active_contracts = getattr(instance, '_active_contracts', None)
        if active_contracts is None:
            active_contracts = list(instance.contracts.filter(is_active=True))
        for contract in active_contracts:
            #if contract.status == active_status:
            if contract.holder:
                holder_str = contract.holder.surname + ', ' + contract.holder.name if contract.holder.name and contract.holder.surname else contract.holder.token
            else:
                holder_str = '-'
            contracts.append({
                'token': contract.token,
                'id': contract.id,
                'status_name': contract.status.name,
                'status_color': contract.status.color,
                'status_token': contract.status.token,
                'holder': holder_str,
            })
        representation['contracts'] = contracts
        
        representation['meter_address_street'] = str(instance.meter.address_street) if instance.meter else None
        representation['last_readings_by_contract'] = []
        try:
            prefetched_readings = getattr(instance, '_prefetched_latest_readings', None)
            for contract in active_contracts:
                latest_reading = None
                if prefetched_readings is not None:
                    latest_reading = prefetched_readings.get(contract.id)
                if latest_reading is None:
                    latest_readings = Reading.objects.filter(
                        supply_point=instance, 
                        contract=contract,
                        is_active=True,
                        is_close=False,
                        is_control=False,
                    ).annotate(
                        latest_date=Max('reading_date')
                    )
                    if latest_readings.exists():
                        latest_reading = latest_readings.order_by('-reading_date').first()
                if latest_reading:
                    representation['last_readings_by_contract'].append({
                        'id': latest_reading.id,
                        'contract_id': contract.id,
                        'reading_value': latest_reading.reading_value,
                        'reading_date': latest_reading.reading_date
                    })

        except Exception as e:
            print(e)
            pass
        
        return representation

class SupplyPointSerializer(serializers.ModelSerializer):
    cluster_nozzle = serializers.SerializerMethodField()
    connection = ConnectionSerializer(required=False, allow_null=True)
    address = serializers.PrimaryKeyRelatedField(queryset=Address.objects.all(), required=False, allow_null=True)
    address_data = serializers.DictField(required=False, allow_null=True, write_only=True)
    observations = SupplyPointObservationSerializer(many=True, required=False, allow_null=True)
    meter = serializers.SerializerMethodField()
    property = PropertySerializer(required=False, allow_null=True)
    placement = SupplyPointPlacementSerializer(required=False, allow_null=True)
    supply_point_children = SupplyPointListSerializer(many=True, required=False, allow_null=True)
    estimated_bag = EstimatedBagMinimalSerializer(required=False, allow_null=True)
    
    supply_point_children_ids = serializers.SerializerMethodField()
    
    # update
    meter_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    connection_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    property_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    property_cadastral = serializers.CharField(write_only=True, required=False, allow_null=True, allow_blank=True)
    placement_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    dismiss_frauds = serializers.BooleanField(write_only=True, required=False, allow_null=True)
    cluster_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    route = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    last_reading = serializers.SerializerMethodField()
    
    current_fraud = serializers.SerializerMethodField()
    previous_fraud = serializers.SerializerMethodField()
    
    active_reading_batch = serializers.SerializerMethodField()
    contract_debt = serializers.SerializerMethodField()
    supply_cut_alert = serializers.SerializerMethodField()

    class Meta:
        model = SupplyPoint
        fields = '__all__'
    
    def get_supply_cut_alert(self, obj):
        return _supply_cut_alert(obj)
    
    def get_contract_debt(self, obj):
        config_tokens = ConfigProject.objects.filter(token__in=[
            'payment_status_paid_token',
            'payment_status_dropped_token',
            'payment_status_cancelled_token',
            'payment_status_payoff_token'
            ])
        active_contracts = obj.contracts.filter(is_active=True).distinct()
        active_contracts_debt = Payment.objects.filter(
            invoice__contract__in=active_contracts,
            status__isnull=False,
            invoice__status__isnull=False
        ).exclude(status__token__in=config_tokens.values_list('value', flat=True)).distinct().aggregate(total=Sum('amount'))['total'] or 0
        return active_contracts_debt
    
    def to_internal_value(self, data):
        # Fem una còpia mutable per poder manipular-la lliurement
        mutable_data = data.copy()
        
        # Si arriba property com objecte o string/int, ho traduïm a property_id
        if 'property' in mutable_data and mutable_data['property'] is not None:
            prop_data = mutable_data.pop('property')
            if isinstance(prop_data, dict) and 'id' in prop_data:
                mutable_data['property_id'] = prop_data['id']
            elif isinstance(prop_data, (int, str)) and str(prop_data).isdigit():
                mutable_data['property_id'] = int(prop_data)
        elif 'property' in mutable_data and mutable_data['property'] is None:
            mutable_data.pop('property')
            mutable_data['property_id'] = None

        # Lògica d'Address: pot arribar address (dict o ID) o address_id (ID)
        # Volem que el Back s'encarregui de fer el find_or_create si és un dict
        address_input = mutable_data.pop('address', None) or mutable_data.pop('address_id', None)
        
        if address_input:
            if isinstance(address_input, dict):
                # Si és un diccionari, usem el AddressSerializer per fer el find_or_create
                addr_serializer = AddressSerializer(data=address_input)
                addr_serializer.is_valid(raise_exception=True)
                address_obj = addr_serializer.save()
                mutable_data['address'] = address_obj.id
            else:
                # Si és un ID (int o string numeric)
                mutable_data['address'] = address_input

        return super().to_internal_value(mutable_data)
    
    def _get_active_reading_batch_status_tokens(self):
        if not hasattr(self, '_active_reading_batch_status_tokens'):
            allow_tokens = [
                'reading_batch_pending_processing_token',
                'reading_batch_processing_token',
                'reading_batch_pending_token',
            ]
            self._active_reading_batch_status_tokens = list(
                ConfigProject.objects.filter(token__in=allow_tokens).values_list('value', flat=True)
            )
        return self._active_reading_batch_status_tokens

    def _active_reading_batch_payload(self, batch):
        return {
            'id': batch.id,
            'token': batch.token,
            'created_at': batch.created_at,
            'status_name': batch.status.name,
            'status_color': batch.status.color,
        }

    def get_active_reading_batch(self, obj):
        status_tokens = self._get_active_reading_batch_status_tokens()
        if not status_tokens:
            return None
        # NOT NEEDED FOR THE MOMENT
        """ reading = (
            Reading.objects.filter(
                supply_point_id=obj.pk,
                batch__isnull=False,
                batch__is_active=True,
                batch__status__token__in=status_tokens,
            )
            .select_related('batch__status')
            .order_by('-batch__created_at')
            .first()
        )
        if reading and reading.batch_id:
            return self._active_reading_batch_payload(reading.batch) """

        return None
    
    def get_last_reading(self, obj):
        reading = Reading.objects.filter(supply_point=obj, is_active=True).order_by('-reading_date').first()
        
        return {
            'id': reading.id,
            'meter_id': reading.meter.id if reading.meter else None,
            'reading_value': reading.reading_value,
            'reading_date': reading.reading_date,
            'calculated_value': reading.calculated_value,
            'real_consumption': reading.real_consumption,
            'consumption_days': reading.consumption_days,
            'leak_value': reading.leak_value,
            'origin': reading.origin,
            'is_estimated': reading.is_estimated,
            'previous_reading': reading.previous_reading.id if reading.previous_reading else None,
            'is_close': reading.is_close,
            'is_control': reading.is_control,
            'is_active': reading.is_active,
        } if reading else None
    
    def get_supply_point_children_ids(self, obj):
        return [child.id for child in obj.supply_point_children.all()]
    
    def get_cluster_nozzle(self, obj):
        from service.serializers.cluster_nozzle_serializer import ClusterNozzleSerializer
        return ClusterNozzleSerializer(obj.cluster_nozzle).data
    
    def get_meter(self, obj):
        # Inclou només els camps essencials per trencar la recursivitat
        if obj.meter:
            return {
                'id': obj.meter.id,
                'code': obj.meter.code  # Afegeix altres camps essencials si és necessari
            }
        return None
    
    def get_current_fraud(self, obj):
        from fraud.models import FraudStatus
        status_pending = FraudStatus.objects.get(token=ConfigProject.objects.get(token="fraud_status_pending_token").value)
        status_active = FraudStatus.objects.get(token=ConfigProject.objects.get(token="fraud_status_active_token").value)
        
        frauds = Fraud.objects.filter(supply_point=obj, status__in=[status_pending, status_active])
        return True if frauds.exists() else False
    
    def get_previous_fraud(self, obj):
        from fraud.models import FraudStatus
        fraud_status_resolved = FraudStatus.objects.get(token=ConfigProject.objects.get(token="fraud_status_resolved_token").value)
        fraud_status_expired = FraudStatus.objects.get(token=ConfigProject.objects.get(token="fraud_status_expired_token").value)
        
        frauds = Fraud.objects.filter(supply_point=obj, status__in=[fraud_status_resolved, fraud_status_expired], is_dismissed=False)
        return True if frauds.exists() else False
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        from contract.serializers.contract_serializer import ContractMinimalSerializer

        # Collect contracts from both relationships
        contracts = []
        """ for contract in instance.default_contracts.all():
            if contract.status == active_status and contract.holder:
                holder_str = ''
                name = contract.holder.name or '-'
                surname = contract.holder.surname or '-'
                if contract.holder.is_juridic:
                    holder_str = name
                else:
                    holder_str = surname + ', ' + name
                #holder_str = contract.holder.surname + ', ' + contract.holder.name if contract.holder.name else contract.holder.surname 
                contracts.append({'token': contract.token, 'id': contract.id, 'status_name': contract.status.name, 'status_color': contract.status.color, 'holder': holder_str, 'holder_token': contract.holder.token}) """
        payment_status_expired = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_expired_token').value)
        payment_status_returned = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_returned_token').value)
        payment_status_pending = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_pending_token').value)
        for contract in instance.contracts.filter(is_active=True):
            #if contract.status == active_status and contract.holder:
            holder_str = ''
            if contract.holder:
                name = contract.holder.name or '-'
                surname = contract.holder.surname or '-'
                if contract.holder.is_juridic:
                    holder_str = name
                else:
                    holder_str = surname + ', ' + name
            else:
                holder_str = '-'
            
            contract_payments = Payment.objects.filter(invoice__contract=contract, status__in=[payment_status_expired,payment_status_returned, payment_status_pending], invoice__status__isnull=False)
            payments_amount = contract_payments.aggregate(total=Sum('amount'))['total'] or 0
            #holder_str = contract.holder.surname + ', ' + contract.holder.name if contract.holder.name else contract.holder.surname
            contracts.append({
                'token': contract.token, 
                'id': contract.id, 
                'status_name': contract.status.name, 
                'status_color': contract.status.color, 
                'status_token': contract.status.token,
                'holder': holder_str, 
                'holder_token': contract.holder.token if contract.holder else None,
                'total_debt': payments_amount
                })
                
        # Add contracts to representation
        representation['contracts'] = contracts

        # Keep other fields
        representation['type'] = SupplyPointTypeSerializer(instance.type).data
        representation['status'] = SupplyPointStatusSerializer(instance.status).data
        representation['source'] = SupplyPointSourceSerializer(instance.source).data
        representation['supply_type'] = SupplyPointSupplyTypeSerializer(instance.supply_type).data
        representation['address'] = AddressSerializer(instance.address).data if instance.address else None
        representation['address_complete'] = str(instance.address)
        representation['meter_id'] = instance.meter.id if instance.meter else None
        representation['meter_code'] = instance.meter.code if instance.meter else None
        representation['property_id'] = instance.property.id if instance.property else None
        def _sp_for_meter(m):
            sp = m.supply_points.first()
            return {"id": sp.id, "token": sp.token, "address_complete": str(sp.address) if sp.address else None} if sp else None
        representation['sub_meters'] = [
            {
                'id': m.id, 'code': m.code,
                'status': MeterStatusSerializer(m.status).data if m.status else None,
                'has_remote_reading': getattr(m, 'has_remote_reading', False),
                'supply_point': _sp_for_meter(m),
            }
            for m in (instance.meter.sub_meters.all() if instance.meter else [])
        ]

        return representation

    def create(self, validated_data):
        validated_data['token'] = generate_token(SupplyPoint)
        address_data = validated_data.pop('address_data') if 'address_data' in validated_data else None
        connection_id = validated_data.pop('connection_id') if 'connection_id' in validated_data else None
        property_id = validated_data.pop('property_id') if 'property_id' in validated_data else None
        property_cadastral = validated_data.pop('property_cadastral', None)
        placement_id = validated_data.pop('placement_id', None)
        placement_data = validated_data.pop('placement', None)
        cluster_id = validated_data.pop('cluster_id', None)
        
        validated_data['cadastral'] = property_cadastral
        print(f"address_data: {address_data}")
        if address_data:
            print(f"address_data found")
            street = Street.objects.get(id=address_data['street']['street_id'])
            street_number = StreetNumber.objects.get(id=address_data['street_number']['street_number_id'])
            city = City.objects.get(id=address_data['city'])
            try:
                province = Province.objects.get(id=address_data['province'])
            except Exception as e:
                print(f"Error getting province: {e}")
                province = city.province
            try:
                country = Country.objects.get(id=address_data['country'])
            except Exception as e:
                print(f"Error getting country: {e}")
                country = province.country
            address_data.pop('city')
            address_data.pop('province')
            address_data.pop('country')
            address_data.pop('street')
            address_data.pop('street_number')
            
            
            try:
                address, created = Address.objects.get_or_create(
                    street = street,
                    street_number = street_number,
                    city = city,
                    province = province,
                    country = country,
                    **address_data
                    )
            except Exception as e:
                print(f"Error getting or creating address: {e}")
                address = Address.objects.filter(street=street, street_number=street_number, **address_data).first()
            
            print(f"address: {address}")
            
        if connection_id:
            connection = Connection.objects.get(id = connection_id)
        else:
            connection = None
        
        # Handle placement - check placement_id first, then placement dict
        placement = None
        if placement_id:
            try:
                placement = SupplyPointPlacement.objects.get(id=placement_id)
            except SupplyPointPlacement.DoesNotExist:
                pass
        elif placement_data:
            if isinstance(placement_data, int):
                try:
                    placement = SupplyPointPlacement.objects.get(id=placement_data)
                except SupplyPointPlacement.DoesNotExist:
                    pass
            elif isinstance(placement_data, dict):
                try:
                    if 'id' in placement_data:
                        placement = SupplyPointPlacement.objects.get(id=placement_data['id'])
                    elif 'code' in placement_data:
                        placement = SupplyPointPlacement.objects.get(id=placement_data['code'])
                    elif 'token' in placement_data:
                        token_value = placement_data['token']
                        # Try by ID first if token is numeric, otherwise try by token field
                        if isinstance(token_value, (int, str)) and str(token_value).isdigit():
                            try:
                                placement = SupplyPointPlacement.objects.get(id=int(token_value))
                            except SupplyPointPlacement.DoesNotExist:
                                placement = SupplyPointPlacement.objects.get(token=token_value)
                        else:
                            placement = SupplyPointPlacement.objects.get(token=token_value)
                except (SupplyPointPlacement.DoesNotExist, Exception):
                    pass
        
        if placement:
            validated_data['placement'] = placement
        
        if property_id:
            property = Property.objects.get(id = property_id)
        else:
            property = None
            
        default_status = SupplyPointStatus.objects.get(is_default=True)
        
        route_position = None
        postal_code_value = address_data.get('postal_code') if address_data else None
        resolved_postal_code = _resolve_postal_code(postal_code_value, city=city if address_data else None)
        if(validated_data.get('route')):
            route = Route.objects.get(id=validated_data.pop('route'))
            route_position = RoutePosition.objects.create(
                position=0,
                route=route,
                token=route.token + '/' + str(street) + '-' + str(street_number) + '-' + (postal_code_value or ''),
                address_street=street,
                address_street_number=street_number,
                address_city=address.city,
                address_postal_code=resolved_postal_code,
                latitude=None,
                longitude=None,
                notebook = None,
                reader_observation = None
            )
        
        if not property:
            postal_code = postal_code_value or ''
            prop_token = generate_token(Property, args=['PROPN'])
            prop_token = check_token_exists(prop_token, Property)
            property = Property.objects.create(
                token = prop_token,
                cadastral = property_cadastral,
                name = (str(street) + ' ' + str(street_number) + ' ' + str(postal_code)).strip(),
                route_position = route_position if route_position else None,
                address_street = street,
                address_street_number = street_number,
                address_postal_code = resolved_postal_code,
                address_city = address.city,
                latitude = None,
                longitude = None,
                is_active = True
            )
            if not route_position:
                auto_assign_route_to_property(property)
        elif route_position:
            property.route_position = route_position
            property.save()
        else:
            auto_assign_route_to_property(property)
        nozzle = None
        if cluster_id:
            cluster = Cluster.objects.get(id = cluster_id)
            last_nozzle = ClusterNozzle.objects.filter(cluster=cluster).order_by('-col').first()
            nozzle = ClusterNozzle.objects.create(
                cluster = cluster,
                token = last_nozzle.token.split('/')[0] + '/' + str(cluster.nb_nozzles + 1),
                status = ClusterNozzleStatus.objects.get(is_default=True),
                type = ClusterNozzleType.objects.get(is_default=True),
                position = cluster.nb_nozzles + 1,
                col=last_nozzle.col + 1 if last_nozzle.col else 1,
                row=1,
                destination=last_nozzle.destination,
                diameter=last_nozzle.diameter,
            )
            cluster.nb_nozzles += 1
            cluster.save()
        
        supply_point = SupplyPoint.objects.create(
            **validated_data,
            address = address,
            connection = connection,
            property = property,
            status = default_status,
            cluster_nozzle = nozzle
        )
            
        return supply_point
    
    def update(self, instance, validated_data):
        
        user = self.context['request'].user
        address_data = validated_data.pop('address_data', None)
        if address_data is not None:
            previous_address = instance.address
            try:
                street = Street.objects.get(id=address_data['street']['street_id'])
                street_number = StreetNumber.objects.get(id=address_data['street_number']['street_number_id'])
                city = City.objects.get(id=address_data['city'])
                province = Province.objects.get(id=address_data['province'])
                country = Country.objects.get(id=address_data['country'])
                
                # Netegem address_data per fer el get_or_create (com al create)
                clean_address_data = address_data.copy()
                for key in ['city', 'province', 'country', 'street', 'street_number']:
                    clean_address_data.pop(key, None)
                
                try:
                    address, created = Address.objects.get_or_create(
                        street = street,
                        street_number = street_number,
                        city = city,
                        province = province,
                        country = country,
                        **clean_address_data
                    )
                except Exception as e:
                    address = Address.objects.filter(
                        street=street, 
                        street_number=street_number, 
                        city=city,
                        province=province,
                        country=country,
                        **clean_address_data
                    ).first()
                
                instance.address = address
                if previous_address != instance.address:
                    supply_point_change_address(user, instance.id, previous_address, instance.address)

            except Exception as e:
                # Fallback per si address_data no té el format esperat de IDs o ja és una instància
                if isinstance(address_data, dict):
                    addr_serializer = AddressSerializer(data=address_data)
                    addr_serializer.is_valid(raise_exception=True)
                    instance.address = addr_serializer.save()
                    if previous_address != instance.address:
                        supply_point_change_address(user, instance.id, previous_address, instance.address)
                else:
                    instance.address = address_data

        
        ## change meter
        if 'meter_id' in validated_data:
            previous_meter = instance.meter
            meter_id = validated_data.pop('meter_id')
            meter = Meter.objects.get(id=meter_id) if meter_id else None
            validated_data['meter'] = meter
            if previous_meter != meter:
                supply_point_change_meter(user, instance.id, previous_meter, meter)
        
        ## change connection
        if validated_data.get('connection_id'):
            previous_connection = instance.connection
            connection = Connection.objects.get(id=validated_data.get('connection_id'))
            validated_data['connection'] = connection
            validated_data.pop('connection_id')
            if previous_connection != connection:
                supply_point_change_connection(user, instance.id, previous_connection, connection)
        
        if validated_data.get('property_id'):
            previous_property = instance.property
            property = Property.objects.get(id=validated_data.get('property_id'))
            validated_data['property'] = property
            validated_data.pop('property_id')
            if previous_property != property:
                supply_point_change_property(user, instance.id, previous_property, property)
        
        if 'dismiss_frauds' in validated_data:
            from fraud.models import FraudStatus
            status_active = FraudStatus.objects.get(token=ConfigProject.objects.get(token="fraud_status_active_token").value)
            validated_data.pop('dismiss_frauds')
            frauds = Fraud.objects.filter(supply_point=instance).exclude(status=status_active)
            frauds.update(is_dismissed=True)
        
        # Gestió específica per al camp placement
        if 'placement' in validated_data:
            placement_value = validated_data.pop('placement')
            if isinstance(placement_value, int):
                # Si placement és un enter, buscar la instància corresponent
                try:
                    placement = SupplyPointPlacement.objects.get(id=placement_value)
                    validated_data['placement'] = placement
                except SupplyPointPlacement.DoesNotExist:
                    # Si no es troba, deixar el placement actual
                    pass
            elif isinstance(placement_value, dict):
                # Si placement és un diccionari, buscar per id, code, o token
                try:
                    placement = None
                    if 'id' in placement_value:
                        placement = SupplyPointPlacement.objects.get(id=placement_value['id'])
                    elif 'code' in placement_value:
                        placement = SupplyPointPlacement.objects.get(id=placement_value['code'])
                    elif 'token' in placement_value:
                        token_value = placement_value['token']
                        # Try by ID first if token is numeric, otherwise try by token field
                        if isinstance(token_value, (int, str)) and str(token_value).isdigit():
                            try:
                                placement = SupplyPointPlacement.objects.get(id=int(token_value))
                            except SupplyPointPlacement.DoesNotExist:
                                placement = SupplyPointPlacement.objects.get(token=token_value)
                        else:
                            placement = SupplyPointPlacement.objects.get(token=token_value)
                    
                    if placement:
                        validated_data['placement'] = placement
                except (SupplyPointPlacement.DoesNotExist, Exception) as e:
                    # Si no es troba, deixar el placement actual
                    pass
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance




class SupplyPointMinimalSerializer(serializers.ModelSerializer):
    current_fraud = serializers.SerializerMethodField()
    status_token = serializers.CharField(source='status.token', read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    supply_cut_alert = serializers.SerializerMethodField()
    contracts = serializers.SerializerMethodField()
    class Meta:
        model = SupplyPoint
        fields = ['id', 'token', 'current_fraud', 'supply_cut_alert', 'status_name', 'status_color', 'status_token' ,'contracts']
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['address_complete'] = str(instance.address)
        representation['meter_id'] = instance.meter.id if instance.meter else None
        representation['meter_code'] = instance.meter.code if instance.meter else None
        if instance.meter:
            representation['is_telecontrol'] = instance.meter.has_remote_reading if instance.meter else False
        representation['distinct_contracts'] = instance.contracts.distinct().count()
        # Sub_meters del contador para mostrarlos anidados en el front (p. ej. en lista de lecturas al editar meter)
        def _sp_for_meter(m):
            sp = m.supply_points.first()
            return {"id": sp.id, "token": sp.token, "address_complete": str(sp.address) if sp.address else None} if sp else None
        representation['sub_meters'] = [
            {
                'id': m.id, 'code': m.code,
                'status': MeterStatusSerializer(m.status).data if m.status else None,
                'has_remote_reading': getattr(m, 'has_remote_reading', False),
                'supply_point': _sp_for_meter(m),
            }
            for m in (instance.meter.sub_meters.all() if instance.meter else [])
        ]
        return representation

    def get_current_fraud(self, obj):
        from fraud.models import FraudStatus
        status_pending = FraudStatus.objects.get(token=ConfigProject.objects.get(token="fraud_status_pending_token").value)
        status_active = FraudStatus.objects.get(token=ConfigProject.objects.get(token="fraud_status_active_token").value)
        
        frauds = Fraud.objects.filter(supply_point=obj, status__in=[status_pending, status_active], contract__isnull=False)
        return True if frauds.exists() else False

    def get_supply_cut_alert(self, obj):
        return _supply_cut_alert(obj)

    def get_contracts(self, obj):
        active_status = _get_active_contract_status()
        contracts = []
        for contract in obj.contracts.filter(is_active=True):
            if contract.status == active_status:
                
                name = str(contract.holder)
                
                contracts.append({
                    'id': contract.id,
                    'token': contract.token,
                    'status_name': contract.status.name,
                    'status_color': contract.status.color,
                    'holder': name
                })
        return contracts

class SupplyPointAppSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplyPoint
        fields = ['id', 'token']
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['address_complete'] = str(instance.address)
        representation['address_id'] = instance.address_id
        representation['meter_id'] = instance.meter.id if instance.meter else None
        representation['meter_code'] = instance.meter.code if instance.meter else None
        return representation

class SupplyPointContractsSerializer(serializers.ModelSerializer):
    current_fraud = serializers.SerializerMethodField()
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    
    class Meta:
        model = SupplyPoint
        fields = ['id', 'token', 'current_fraud', 'status_name', 'status_color']
        
    def get_current_fraud(self, obj):
        from fraud.models import FraudStatus
        status_pending = FraudStatus.objects.get(token=ConfigProject.objects.get(token="fraud_status_pending_token").value)
        status_active = FraudStatus.objects.get(token=ConfigProject.objects.get(token="fraud_status_active_token").value)
        
        frauds = Fraud.objects.filter(supply_point=obj, status__in=[status_pending, status_active], contract__isnull=False)
        return True if frauds.exists() else False
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        from contract.serializers.contract_serializer import ContractListSerializer
        
        if instance.meter:
            representation['is_telecontrol'] = instance.meter.has_remote_reading if instance.meter else False
        representation['meter_id'] = instance.meter.id if instance.meter else None
        
        active_status = _get_active_contract_status()
        
        contracts = []
        
        for contract in instance.default_contracts.filter(is_active=True):
            if contract.status == active_status:
                contracts.append(ContractListSerializer(contract, context=self.context).data)
        
        for contract in instance.contracts.filter(is_active=True):
            if contract.status == active_status:
                contracts.append(ContractListSerializer(contract, context=self.context).data)
        
        representation['contracts'] = contracts
        representation['address_complete'] = str(instance.address)
        representation['address_id'] = instance.address.id if instance.address else None
        
        try:
            reading = Reading.objects.filter(
                supply_point=instance, is_active=True, is_close=False, is_control=False
            ).order_by('-reading_date').first()
            meter_reading = Reading.objects.filter(
                meter=instance.meter, is_active=True, is_close=False, is_control=False
            ).order_by('-reading_date').first()
        except Exception as e:
            reading = None
            meter_reading = None
            
        representation['last_reading'] = {
            'id': reading.id,
            'reading_date': reading.reading_date,
            'reading_value': reading.reading_value,
            'consumption_days': reading.consumption_days,
            'is_estimated': reading.is_estimated,
            'contract_request_id': reading.contract_request.id if reading.contract_request else None,
            'is_initial': reading.is_initial,
            'meter_id': reading.meter.id if reading.meter else None,
            'alert': reading.alert.name if reading.alert else None,
            'alert_notes': reading.alert_notes,
        } if reading else None
        representation['last_meter_reading'] = {
            'id': meter_reading.id,
            'reading_date': meter_reading.reading_date,
            'reading_value': meter_reading.reading_value,
            'consumption_days': meter_reading.consumption_days,
            'is_estimated': meter_reading.is_estimated,
            'contract_request_id': meter_reading.contract_request.id if meter_reading.contract_request else None,
            'is_initial': meter_reading.is_initial,
            'meter_id': meter_reading.meter.id if meter_reading.meter else None,
            'alert': meter_reading.alert.name if meter_reading.alert else None,
            'alert_notes': meter_reading.alert_notes,
        } if meter_reading else None
        
        return representation

class SupplyPointMinimalContractsSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = SupplyPoint
        fields = ['id', 'token']
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        from contract.serializers.contract_serializer import ContractMinimalSerializer
        
        active_status = _get_active_contract_status()
        active_contract_token = active_status.token
        
        if instance.meter:
            representation['is_telecontrol'] = instance.meter.has_remote_reading if instance.meter else False
        representation['meter_id'] = instance.meter.id if instance.meter else None
        
        contracts = []
        
        for contract in instance.default_contracts.filter(is_active=True, status__token=active_contract_token):
            #if contract.status == active_status:
            contracts.append(ContractMinimalSerializer(contract, context=self.context).data)
        
        for contract in instance.contracts.filter(is_active=True, status__token=active_contract_token):
            #if contract.status == active_status:
            contracts.append(ContractMinimalSerializer(contract, context=self.context).data)
                
        # Get the last reading for each contract associated with this supply point
        representation['last_readings_by_contract'] = []
        try:
            # Get the latest reading for each contract associated with this supply point
            # This ensures we get the most recent reading for each different contract
            latest_readings = Reading.objects.filter(
                supply_point=instance, 
                is_active=True,
                is_close=False,
                is_control=False,
                contract__isnull=False,  # Ensure we only get readings with contracts
                contract__is_active=True,
                contract__status__token=active_contract_token,
            ).values('contract').annotate(
                latest_date=Max('reading_date')
            )
            
            for latest in latest_readings:
                if latest['contract']:
                    # Get the most recent reading for this contract on the latest date
                    reading = Reading.objects.filter(
                        supply_point=instance,
                        is_active=True,
                        is_close=False,
                        contract_id=latest['contract'],
                        reading_date=latest['latest_date'],
                        is_control=False,
                    ).order_by('-created_at').first() 
                    
                    if reading:
                        representation['last_readings_by_contract'].append({
                            'id': reading.id,
                            'contract_id': reading.contract.id,
                            'reading_value': reading.reading_value,
                            'reading_date': reading.reading_date,
                            'meter_code': reading.meter.code if reading.meter else None,
                            'reader_alert': reading.reader_alert.name if reading.reader_alert else None,
                            'remote_alert': reading.remote_alert.name if reading.remote_alert else None,
                            'remote_alert_object': RemoteReadingAlertSerializer(reading.remote_alert).data if reading.remote_alert else None,
                            'previous_reading_value': reading.previous_reading.reading_value if reading.previous_reading else None,
                            'previous_reading_date': reading.previous_reading.reading_date if reading.previous_reading else None,
                            'photo': self._encode_photo_to_base64(reading.photo) if reading.photo else None
                        })
            
        except Exception as e:
            # Log the exception for debugging if needed
            pass
        
        # Keep the old field for backward compatibility, but use the first reading if available
        first_reading = representation['last_readings_by_contract'][0] if representation['last_readings_by_contract'] else None
        representation['last_reading_value'] = first_reading['reading_value'] if first_reading else 0
        representation['last_reading_date'] = first_reading['reading_date'] if first_reading else None
        representation['last_meter_code'] = first_reading['meter_code'] if first_reading else None
        representation['last_reader_alert'] = first_reading['reader_alert'] if first_reading else None
        representation['last_remote_alert'] = first_reading['remote_alert'] if first_reading else None
        representation['last_previous_reading_value'] = first_reading['previous_reading_value'] if first_reading else None
        representation['last_previous_reading_date'] = first_reading['previous_reading_date'] if first_reading else None
        representation['last_remote_alert_object'] = first_reading['remote_alert_object'] if first_reading else None
        representation['supply_status_name'] = instance.status.name if instance.status else None
        representation['supply_status_color'] = instance.status.color if instance.status else None
        representation['contracts'] = contracts
        
        if first_reading:
            representation['photo'] = first_reading["photo"] if first_reading["photo"] else None
        
        representation['address_complete'] = str(instance.address)
        
        return representation
    
    def _encode_photo_to_base64(self, photo):
        """Helper method to encode photo to base64"""
        try:
            if photo and hasattr(photo, 'read'):
                # Read the file content
                photo.seek(0)  # Reset file pointer to beginning
                image_data = photo.read()
                # Encode to base64
                encoded_image = base64.b64encode(image_data).decode('utf-8')
                return encoded_image
            return None
        except Exception as e:
            print(f"Error encoding photo to base64: {e}")
            return None


class FlexibleForeignKeyField(serializers.Field):
    """Custom field that handles both PK and dict inputs for foreign key relationships"""
    
    def __init__(self, model_class, **kwargs):
        self.model_class = model_class
        super().__init__(**kwargs)
    
    def to_internal_value(self, data):
        if data is None:
            return None
        
        if isinstance(data, dict):
            if 'id' in data:
                try:
                    return self.model_class.objects.get(id=data['id'])
                except self.model_class.DoesNotExist:
                    raise serializers.ValidationError(f"{self.model_class.__name__} with id {data['id']} not found")
            elif 'code' in data:
                try:
                    return self.model_class.objects.get(id=data['code'])
                except self.model_class.DoesNotExist:
                    raise serializers.ValidationError(f"{self.model_class.__name__} with code {data['code']} not found")
            elif 'token' in data:
                token_value = data['token']
                # Try by ID first if token is numeric, otherwise try by token field
                if isinstance(token_value, (int, str)) and str(token_value).isdigit():
                    try:
                        return self.model_class.objects.get(id=int(token_value))
                    except self.model_class.DoesNotExist:
                        try:
                            return self.model_class.objects.get(token=token_value)
                        except self.model_class.DoesNotExist:
                            raise serializers.ValidationError(f"{self.model_class.__name__} with token {token_value} not found")
                else:
                    try:
                        return self.model_class.objects.get(token=token_value)
                    except self.model_class.DoesNotExist:
                        raise serializers.ValidationError(f"{self.model_class.__name__} with token {token_value} not found")
        elif isinstance(data, int):
            try:
                return self.model_class.objects.get(id=data)
            except self.model_class.DoesNotExist:
                raise serializers.ValidationError(f"{self.model_class.__name__} with id {data} not found")
        
        # If it's already a model instance, return it
        return data
    
    def to_representation(self, value):
        if value is None:
            return None
        return {
            'id': value.id,
            'token': getattr(value, 'token', None),
            'name': getattr(value, 'name', None),
            'code': getattr(value, 'code', None),
            'label': getattr(value, 'label', None)
        }

class SupplyPointSaveNozzleSerializer(serializers.ModelSerializer):
    """
    Custom serializer for SupplyPoint that works with the existing data structure
    from the frontend, handling nested StreetType and StreetNumberType objects.
    """
    address = serializers.DictField(required=False, allow_null=True)
    placement = FlexibleForeignKeyField(SupplyPointPlacement, required=False, allow_null=True)
    type = FlexibleForeignKeyField(SupplyPointType, required=False, allow_null=True)
    source = FlexibleForeignKeyField(SupplyPointSource, required=False, allow_null=True)
    supply_type = FlexibleForeignKeyField(SupplyPointSupplyType, required=False, allow_null=True)
    
    class Meta:
        model = SupplyPoint
        fields = '__all__'
    
    def create(self, validated_data):
        # Extract address data
        address_data = validated_data.pop('address', None)
        
        # Handle address
        if address_data and isinstance(address_data, dict):
            address = self._create_address(address_data)
            validated_data['address'] = address
        
        # Create the SupplyPoint
        return super().create(validated_data)
    
    def _create_address(self, address_data):
        """Create Address from the nested data structure"""
        street_data = address_data.get('street') or {}
        street_number_data = address_data.get('street_number') or {}
        
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
                street.save()
            else:
                street, _ = Street.objects.get_or_create(
                    name=street_data.get('name', ''),
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
        
        # Normalize optional string fields: treat None as empty string
        postal_code = address_data.get('postal_code') or ''
        building = address_data.get('building') or ''
        floor = address_data.get('floor') or ''
        door = address_data.get('door') or ''
        stair = address_data.get('stair') or ''

        # Create Address
        if Address.objects.filter(street=street,
            street_number=street_number,
            city=city,
            province=province,
            country=country,
            postal_code=postal_code,
            building=building,
            floor=floor,
            door=door,
            stair=stair).exists():
            
            address = Address.objects.filter(street=street,
                street_number=street_number,
                city=city,
                province=province,
                country=country,
                postal_code=postal_code,
                building=building,
                floor=floor,
                door=door,
                stair=stair).first()
        else:
            address = Address.objects.create(
                street=street,
                street_number=street_number,
                city=city,
                province=province,
                country=country,
                postal_code=postal_code,
                building=building,
                floor=floor,
                door=door,
                stair=stair
            )
        
        return address