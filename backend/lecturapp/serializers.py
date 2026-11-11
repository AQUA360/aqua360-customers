import base64
from rest_framework import serializers
from django.db.models import Count, Q

from billing.models import Reading, ReadingBatch
from billing.serializers.reading_batch_serializer import ReadingBatchStatusSerializer
from billing.serializers.reading_serializer import ReaderAlertSerializer
from billing.utils.reading_service import get_average_consumption
from coredata.models import ConfigProject
from service.models import Meter, Property, Route, RoutePosition, SupplyPoint
from service.serializers.route_serializer import RouteZoneSerializer
from service.utils.route_scope import (
    effective_route_position,
    effective_route_position_expr,
    position_supply_points_q,
    route_supply_points_q,
    routes_supply_points_q,
)
from statistics.models import ContractConsumption
from .models import ReadingOperator


def _reading_mode_flags(context):
    include_telecontrol = bool(context.get('include_telecontrol', False))
    include_manual = context.get('include_manual', True)
    return include_telecontrol, bool(include_manual)


def _position_properties(position, supply_point_filter=Q()):
    """Finques amb algun punt que pertany efectivament a la posició, més les
    finques de la posició que encara no tenen cap punt.

    Inclou les finques d'altres posicions si tenen un punt amb aquesta posició
    pròpia, i exclou les finques de la posició si tots els seus punts són en
    una altra ruta.
    """
    supply_points = SupplyPoint.objects.filter(position_supply_points_q(position)).filter(supply_point_filter)
    return Property.objects.filter(
        Q(supply_points__in=supply_points) | Q(route_position=position, supply_points__isnull=True)
    ).distinct()


def _property_supply_points(instance, context):
    """Punts de la finca; si el context porta `route_position`, només els que
    pertanyen efectivament a aquesta posició."""
    supply_points = instance.supply_points.all()
    route_position = context.get('route_position')
    if route_position is not None:
        supply_points = supply_points.filter(position_supply_points_q(route_position))
    return supply_points


# Motius pels quals un comptador s'envia a l'app però no es pot llegir: l'app
# el mostra deshabilitat perquè el lector vegi la boquilla sencera i se'l salti.
DISABLED_OTHER_ROUTE = 'other_route'
DISABLED_SUPPLY_POINT_INACTIVE = 'supply_point_inactive'
DISABLED_METER_INACTIVE = 'meter_inactive'
DISABLED_NO_METER = 'no_meter'


def _config_value(context, token):
    """Valor de ConfigProject, desat al context per no repetir la consulta."""
    cache = context.setdefault('_config_cache', {}) if isinstance(context, dict) else {}
    if token not in cache:
        config = ConfigProject.objects.filter(token=token).first()
        cache[token] = config.value if config else None
    return cache[token]


def active_supply_point_q(active_token, prefix=''):
    """Punts actius (o sense estat): els de baixa no es llegeixen."""
    return Q(**{f'{prefix}status__isnull': True}) | Q(**{f'{prefix}status__token': active_token})


def _meter_matches_mode(meter, include_telecontrol, include_manual):
    is_telecontrol = bool(meter.has_remote_reading) and not bool(meter.force_manual_reading)
    if not include_telecontrol:
        return not is_telecontrol
    if not include_manual:
        return is_telecontrol
    return True


def property_meter_entries(property_obj, context):
    """Comptadors de tots els punts de la finca, en l'ordre dels punts, amb el
    motiu pel qual no es poden llegir en aquesta posició (None si es poden
    llegir). Només s'hi deixen els que encaixen amb el mode del lot
    (telelectura o lectura manual)."""
    cache = context.setdefault('_meter_entries_cache', {})
    route_position = context.get('route_position')
    key = (property_obj.pk, route_position.pk if route_position else None)
    if key in cache:
        return cache[key]

    include_telecontrol, include_manual = _reading_mode_flags(context)
    active_token = _config_value(context, 'supply_point_status_activate_token')
    no_meter_token = _config_value(context, 'token_meter_status_no_meter')

    supply_points = property_obj.supply_points.select_related(
        'meter__status', 'status', 'address', 'cluster_nozzle__cluster',
        'route_position__route', 'property__route_position__route',
    ).order_by('id')
    in_position_ids = None
    if route_position is not None:
        in_position_ids = set(
            supply_points.filter(position_supply_points_q(route_position)).values_list('id', flat=True)
        )

    entries = []
    seen_meter_ids = set()
    for supply_point in supply_points:
        meter = supply_point.meter
        if not meter or meter.id in seen_meter_ids:
            continue
        if not _meter_matches_mode(meter, include_telecontrol, include_manual):
            continue
        seen_meter_ids.add(meter.id)
        meter_token = meter.status.token if meter.status else None
        if meter_token is None or meter_token == '-1':
            reason = DISABLED_METER_INACTIVE
        elif meter_token == no_meter_token:
            reason = DISABLED_NO_METER
        elif supply_point.status_id and supply_point.status.token != active_token:
            reason = DISABLED_SUPPLY_POINT_INACTIVE
        elif in_position_ids is not None and supply_point.id not in in_position_ids:
            reason = DISABLED_OTHER_ROUTE
        else:
            reason = None
        entries.append((supply_point, meter, reason))
    cache[key] = entries
    return entries


def cluster_fields(supply_point):
    nozzle = supply_point.cluster_nozzle if supply_point else None
    if not nozzle or not nozzle.cluster:
        return {'has_cluster': False}
    return {
        'has_cluster': True,
        'cluster_nozzle_col': nozzle.col if nozzle.col else nozzle.position,
        'cluster_nozzle_row': nozzle.row if nozzle.row else 1,
        'cluster_position': nozzle.position if nozzle.position else 1,
        'cluster_token': nozzle.cluster.token,
    }


def disabled_meter_data(supply_point, meter, reason, context):
    """Dades mínimes d'un comptador que l'app mostra deshabilitat."""
    data = {
        'id': meter.id,
        'code': meter.code,
        'code2': meter.code2,
        'caliber': meter.caliber_id,
        'comm_module': meter.comm_module,
        'has_remote_reading': meter.has_remote_reading,
        'reader_observation': supply_point.reader_observation,
        'supply_address': str(supply_point.address) if supply_point.address else None,
        'supply_token': supply_point.token,
        'supply_placement_id': supply_point.placement_id,
        'contract_token': None,
        'holder_name': None,
        'min_value': None,
        'max_value': None,
        'reading_batch_id': context.get('reading_batch_id'),
        'new_reading': None,
        'new_reading_date': None,
        'new_photo': None,
        'reader_alert': None,
        'last_reading': None,
        'previous_reading_id': None,
        'is_readable': False,
        'disabled_reason': reason,
        'other_route_token': None,
        'other_position_token': None,
    }
    data.update(cluster_fields(supply_point))
    if reason == DISABLED_OTHER_ROUTE:
        position = effective_route_position(supply_point)
        if position:
            data['other_route_token'] = position.route.token if position.route_id else None
            data['other_position_token'] = position.token
    return data


def _batch_readable_supply_points(reading_batch):
    active_token = _config_value({}, 'supply_point_status_activate_token')
    return SupplyPoint.objects.filter(routes_supply_points_q(reading_batch.routes.all())).filter(
        active_supply_point_q(active_token))


def _route_readable_supply_points(route, context):
    active_token = _config_value(context, 'supply_point_status_activate_token')
    return SupplyPoint.objects.filter(route_supply_points_q(route)).filter(active_supply_point_q(active_token))


# App users and authentication

class ReadingOperatorSerializer(serializers.ModelSerializer):
    """Serializer for ReadingOperator model"""
    
    class Meta:
        model = ReadingOperator
        fields = ['id', 'name', 'surname', 'username', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class ReadingOperatorCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating ReadingOperator with password"""
    
    password = serializers.CharField(write_only=True, min_length=6)
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = ReadingOperator
        fields = ['name', 'surname', 'username', 'password', 'password_confirm']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        return ReadingOperator.objects.create(**validated_data)

class ReadingOperatorUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating ReadingOperator"""
    
    class Meta:
        model = ReadingOperator
        fields = ['name', 'surname', 'username', 'is_active']

class ReadingOperatorPasswordChangeSerializer(serializers.Serializer):
    """Serializer for changing password"""
    
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=6)
    new_password_confirm = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("New passwords don't match")
        return attrs

class AuthenticationSerializer(serializers.Serializer):
    """Serializer for authentication"""
    
    username = serializers.CharField()
    password = serializers.CharField(write_only=True) 
    
# App info


class ReadingBatchAppSerializer(serializers.ModelSerializer):
    status = ReadingBatchStatusSerializer(read_only=True, required=False, allow_null=True)
    num_routes = serializers.SerializerMethodField()
    num_properties = serializers.SerializerMethodField()
    num_meters = serializers.SerializerMethodField()
    num_readings = serializers.SerializerMethodField()

    class Meta:
        model = ReadingBatch
        fields = [
            'id',
            'status',
            'name',
            'token',
            'num_routes',
            'num_properties',
            'num_meters',
            'num_readings',
        ]
    
    def get_num_routes(self, obj):
        if obj.fix_meters.count() > 0:
            return 1
        else:
            return obj.routes.count()
    
    def get_num_properties(self, obj):
        token_meter_status_no_meter = ConfigProject.objects.get(token='token_meter_status_no_meter').value
        excluded_tokens = [token_meter_status_no_meter, '-1']

        if obj.fix_meters.count() > 0:
            return obj.fix_meters.aggregate(
                total=Count('supply_points__property', distinct=True)
            )['total'] or 0
        
        if obj.include_telecontrol and not obj.include_manual:
            main_filter = (
                Q(meter__status__token__isnull=False) &
                Q(meter__has_remote_reading=True, meter__force_manual_reading=False) & 
                ~Q(meter__status__token__in=excluded_tokens)
            )
        elif obj.include_manual and not obj.include_telecontrol:
            main_filter = (
                Q(meter__status__token__isnull=False) &
                ~Q(meter__status__token__in=excluded_tokens) &
                ( Q(meter__has_remote_reading=False) |
                    Q(meter__force_manual_reading=True))
            )
        else:
            main_filter = (
                Q(meter__status__token__isnull=False) &
                ~Q(meter__status__token__in=excluded_tokens)
            )

        # Punts actius amb ruta efectiva a les rutes del lot (propis o heretats de la finca)
        batch_supply_points = _batch_readable_supply_points(obj)
        return batch_supply_points.aggregate(
            total=Count(
                'property',
                filter=main_filter,
                distinct=True,
            )
        )['total'] or 0
    
    def get_num_meters(self, obj):
        # Count meters excluding those with status token '-1'
        token_meter_status_no_meter = ConfigProject.objects.get(token='token_meter_status_no_meter').value
        if obj.fix_meters.count() > 0:
            return obj.fix_meters.count()
        else:
            batch_supply_points = _batch_readable_supply_points(obj)
            if obj.include_telecontrol and not obj.include_manual:
                main_meters = batch_supply_points.aggregate(
                    total=Count('meter',
                            filter=(Q(meter__status__token__isnull=False) & 
                                  Q(meter__has_remote_reading=True, meter__force_manual_reading=False) & 
                                    ~Q(meter__status__token__in=[token_meter_status_no_meter, '-1'])),
                            distinct=True)
                )['total'] or 0
            elif obj.include_manual and not obj.include_telecontrol:
                main_meters = batch_supply_points.aggregate(
                    total=Count('meter',
                            filter=(Q(meter__status__token__isnull=False) & 
                                    ~Q(meter__status__token__in=[token_meter_status_no_meter, '-1']) &
                                    (Q(meter__has_remote_reading=False) | Q(meter__force_manual_reading=True))),
                            distinct=True)
                )['total'] or 0
            else:
                main_meters = batch_supply_points.aggregate(
                    total=Count('meter',
                            filter=(Q(meter__status__token__isnull=False) &
                                    ~Q(meter__status__token__in=[token_meter_status_no_meter, '-1'])),
                            distinct=True)
                )['total'] or 0
            return main_meters
    
    def get_num_readings(self, obj):
        return obj.readings.filter(copied_from__isnull=True).count()
    
# ROUTE POSITIONS
    
class RoutePositionAppSerializer(serializers.ModelSerializer):
    # read
    properties = serializers.SerializerMethodField()
    
    class Meta:
        model = RoutePosition
        fields = '__all__'
    
    def get_properties(self, obj):
        # Pass context down to PropertyAppSerializer
        
        exclude_telecontrol = not self.context.get('include_telecontrol', False)
        if exclude_telecontrol:
            properties = _position_properties(obj, Q(meter__has_remote_reading=False) | Q(meter__force_manual_reading=True))
        else:
            properties = _position_properties(obj)
        
        context = {**self.context, 'route_position': obj}
        return PropertyAppSerializer(properties, many=True, context=context).data

class RoutePositionAppDetailedSerializer(serializers.ModelSerializer):
    # read
    properties = serializers.SerializerMethodField()
    
    class Meta:
        model = RoutePosition
        fields = '__all__'
    
    def get_properties(self, obj):
        context = {**self.context, 'route_position': obj}
        return PropertyAppDetailedSerializer(_position_properties(obj), many=True, context=context).data
    
# ROUTES

class RouteAppSerializer(serializers.ModelSerializer):
    route_zone = RouteZoneSerializer(required=False, allow_null=True)
    positions = serializers.SerializerMethodField()
    num_properties = serializers.SerializerMethodField()
    num_meters = serializers.SerializerMethodField()

    def get_num_properties(self, obj):
        # Calculate the number of properties using database aggregation
        exclude_telecontrol = not self.context.get('include_telecontrol', False)
        token_meter_status_no_meter = ConfigProject.objects.get(token='token_meter_status_no_meter').value
        excluded_tokens = [token_meter_status_no_meter, '-1']
        if not exclude_telecontrol:
            main_filter = (
                Q(meter__status__token__isnull=False) &
                Q(meter__has_remote_reading=True, meter__force_manual_reading=False) & 
                ~Q(meter__status__token__in=excluded_tokens)
            )
        else:
            main_filter = (
                Q(meter__status__token__isnull=False) &
                ~Q(meter__status__token__in=excluded_tokens) &
                (Q(meter__has_remote_reading=False) | Q(meter__force_manual_reading=True))
            )
        return _route_readable_supply_points(obj, self.context).aggregate(
            count=Count('property',
                        filter=main_filter,
                        distinct=True)
        )['count'] or 0
    
    def get_num_meters(self, obj):
        # Calculate the number of unique meters using database aggregation (excluding meters with status token '-1')

        exclude_telecontrol = not self.context.get('include_telecontrol', False)
        token_meter_status_no_meter = ConfigProject.objects.get(token='token_meter_status_no_meter').value
        # Build the filter for main meters
        main_meter_filter = Q(meter__status__token__isnull=False) & ~Q(meter__status__token__in=[token_meter_status_no_meter,'-1'])
        if exclude_telecontrol:
            main_meter_filter &= (Q(meter__has_remote_reading=False) | Q(meter__force_manual_reading=True)) & ~Q(meter__status__token__in=[token_meter_status_no_meter,'-1'])
        else:
            main_meter_filter &= Q(meter__has_remote_reading=True, meter__force_manual_reading=False) & ~Q(meter__status__token__in=[token_meter_status_no_meter,'-1'])
        
        # Count main meters
        main_meters_count = _route_readable_supply_points(obj, self.context).aggregate(
            count=Count('meter', 
                       filter=main_meter_filter, 
                       distinct=True)
        )['count'] or 0
        
        return main_meters_count
    
    class Meta:
        model = Route
        fields = ['id', 'name', 'positions', 'num_properties', 'num_meters', 'route_zone']
    
    def get_positions(self, obj):
        # Use prefetch_related data to avoid N+1 queries
        if hasattr(obj, '_prefetched_objects_cache') and 'positions' in obj._prefetched_objects_cache:
            # Return only the first 5 positions ordered by "position"
            positions = obj.positions.all().order_by('position')[:5]
            return RoutePositionAppSerializer(positions, many=True, context=self.context).data
        return obj.positions.values_list('id', flat=True)
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        return representation
    
class RouteAppDetailSerializer(serializers.ModelSerializer):
    route_zone = RouteZoneSerializer(required=False, allow_null=True)
    positions = serializers.SerializerMethodField()
    class Meta:
        model = Route
        fields = '__all__'
        
    def get_positions(self, obj):
        # Pass context down to RoutePositionAppSerializer
        include_telecontrol, include_manual = _reading_mode_flags(self.context)
        token_meter_status_no_meter = ConfigProject.objects.get(token='token_meter_status_no_meter').value
        # Posicions amb algun comptador vàlid entre els punts que hi pertanyen
        # efectivament (posició pròpia del punt o, si no en té, la de la finca)
        active_token = _config_value(self.context, 'supply_point_status_activate_token')
        supply_points = SupplyPoint.objects.filter(
            route_supply_points_q(obj), meter__status__isnull=False,
        ).filter(active_supply_point_q(active_token)).exclude(
            meter__status__token__in=[token_meter_status_no_meter, '-1'])
        if not include_telecontrol:
            supply_points = supply_points.filter(Q(meter__has_remote_reading=False) | Q(meter__force_manual_reading=True))
        elif not include_manual:
            supply_points = supply_points.filter(meter__has_remote_reading=True, meter__force_manual_reading=False)
        position_ids = supply_points.annotate(
            effective_position=effective_route_position_expr()
        ).values('effective_position')
        positions_filtered = list(obj.positions.filter(id__in=position_ids))
        return RoutePositionAppDetailedSerializer(positions_filtered, many=True, context=self.context).data
    
# PROPERTIES

class PropertyAppDetailedSerializer(serializers.ModelSerializer):
    meters = serializers.SerializerMethodField()
    class Meta:
        model = Property
        fields = '__all__'

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        batch_readings = self.context.get('batch_readings', [])

        # Només compten els comptadors que es poden llegir en aquesta posició
        meter_ids = {
            meter.id for _, meter, reason in property_meter_entries(instance, self.context) if reason is None
        }

        representation['num_meters'] = len(meter_ids)
        
        # Use pre-fetched batch readings for counting
        if batch_readings:
            representation['num_readings'] = sum(1 for reading in batch_readings if reading.meter_id in meter_ids)
        else:
            representation['num_readings'] = 0
        
        representation['latitude'] = instance.latitude if instance.latitude else 0
        representation['longitude'] = instance.longitude if instance.longitude else 0
        
        representation['address_complete'] = str(instance.address_street) + ' ' + str(instance.address_street_number)
        return representation
   
    def get_meters(self, obj):
        """Comptadors de la finca que es poden llegir en aquesta posició. Si
        l'app ho demana (`include_disabled_meters`), també els d'una altra
        ruta, els de punts de baixa i els inactius o sense comptador, marcats
        com a no llegibles perquè els mostri deshabilitats."""
        entries = property_meter_entries(obj, self.context)
        if not self.context.get('include_disabled_meters'):
            entries = [entry for entry in entries if entry[2] is None]
        readable = [meter for _, meter, reason in entries if reason is None]
        serialized = {item['id']: item for item in MeterAppSerializer(readable, many=True, context=self.context).data}
        meters = []
        for supply_point, meter, reason in entries:
            if reason is None:
                meters.append({
                    **serialized[meter.id], 'is_readable': True, 'disabled_reason': None,
                    'other_route_token': None, 'other_position_token': None,
                })
            else:
                meters.append(disabled_meter_data(supply_point, meter, reason, self.context))
        return meters


class PropertyAppSerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = '__all__'

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        reading_batch_id = self.context.get('reading_batch_id')
        batch_readings = self.context.get('batch_readings', [])
        token_meter_status_no_meter = ConfigProject.objects.get(token='token_meter_status_no_meter').value
        exclude_telecontrol = not self.context.get('include_telecontrol', False)
        
        num_readings = 0
        num_meters = 0
        
        supply_points = _property_supply_points(instance, self.context)
        if exclude_telecontrol:
            supply_points = supply_points.filter(Q(meter__has_remote_reading=False) | Q(meter__force_manual_reading=True)).distinct()
        else:
            supply_points = supply_points.distinct()
        
        # Count supply points and readings using pre-fetched data (excluding meters with status token '-1')
        for supply_point in supply_points:
            if supply_point.meter:
                # Only count meter if status token is neither no_meter nor inactive '-1'
                if supply_point.meter.status and supply_point.meter.status.token not in [token_meter_status_no_meter, '-1']:
                    num_meters += 1
                # Check if meter has reading in batch
                if any(reading.meter_id == supply_point.meter.id for reading in batch_readings):
                    num_readings += 1
                     
        representation['num_meters'] = num_meters
        representation['num_readings'] = num_readings
        
        representation['latitude'] = instance.latitude if instance.latitude else 0
        representation['longitude'] = instance.longitude if instance.longitude else 0
        
        representation['address_complete'] = str(instance.address_street) + ' ' + str(instance.address_street_number)
        return representation
    
# METER

       
class MeterAppSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meter
        fields = ['id', 'code', 'code2', 'caliber', 'comm_module', 'has_remote_reading']
        
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        reading_batch_id = self.context.get('reading_batch_id')
        
        # Check if this meter was already serialized (cached) to avoid redundant work
        cache = self.context.get('serialized_meters_cache')
        # if cache is not None and instance.id in cache:
        #     return cache[instance.id]
        
        # Update progress for each unique meter serialized
        progress_recorder = self.context.get('progress_recorder')
        seen_meter_ids = self.context.get('seen_meter_ids')
        if progress_recorder and seen_meter_ids is not None:
            if instance.id not in seen_meter_ids:
                seen_meter_ids.add(instance.id)
                if not hasattr(progress_recorder, '_meter_count'):
                    progress_recorder._meter_count = 0
                progress_recorder._meter_count += 1
                
                total_meters = self.context.get('total_meters', 1)
                if total_meters > 0:
                    progress_ratio = min(progress_recorder._meter_count / total_meters, 1.0)
                    progress_percentage = 30 + (progress_ratio * 65)
                else:
                    progress_percentage = 30
                progress_recorder.set_progress(int(progress_percentage), 100, f"Serialized {progress_recorder._meter_count}/{total_meters} meters...")
        
        # Use pre-fetched supply point data
        supply_point = instance.supply_points.first()
        
        # Initialize min_value and max_value with default values
        min_value = None
        max_value = None
        
        if supply_point:
            # Use pre-fetched contracts
            
            month = self.context.get('month')
            
            contract = None
            contract_active_token = self.context.get('contract_active_token')
            if contract_active_token is None:
                contract_active_token = ConfigProject.objects.get(token='contract_active_token').value
                self.context['contract_active_token'] = contract_active_token
            if hasattr(supply_point, '_prefetched_objects_cache') and 'contracts' in supply_point._prefetched_objects_cache:
                for c in supply_point.contracts.all():
                    if c.is_active and c.status and c.status.token == contract_active_token:
                        contract = c
                        break
            else:
                contract = supply_point.contracts.filter(is_active=True, status__token=contract_active_token).first()
            
            if contract:
                avg_consumption = get_average_consumption(contract, month)
            
                if avg_consumption:
                    avg_consumption_value = float(avg_consumption)
                    min_value = avg_consumption_value * 0.3
                    max_value = avg_consumption_value * 1.7
                else:
                    min_consumption = ConfigProject.objects.filter(token='minimum_consumption').first()
                    value = float(min_consumption.value) if min_consumption else 6
                    min_value = value * 0.3
                    max_value = value * 1.7
            else:
                # If no contract, use default minimum consumption values
                min_consumption = ConfigProject.objects.filter(token='minimum_consumption').first()
                value = float(min_consumption.value) if min_consumption else 6
                min_value = value * 0.3
                max_value = value * 1.7
            
            representation['reader_observation'] = supply_point.reader_observation
            representation['supply_address'] = str(supply_point.address) if supply_point.address else None
            representation['supply_token'] = supply_point.token
            representation['supply_placement_id'] = supply_point.placement.id if supply_point.placement else None
            representation['contract_token'] = contract.token if contract else None
            # Safely concatenate holder name and surname, handling None values
            if contract and contract.holder:
                name = contract.holder.name or ''
                surname = contract.holder.surname or ''
                representation['holder_name'] = f"{name} {surname}".strip() or None
            else:
                representation['holder_name'] = None
        else:
            representation['reader_observation'] = None
            representation['supply_address'] = None
            representation['supply_token'] = None
            representation['supply_placement_id'] = None
            representation['contract_token'] = None
            representation['holder_name'] = None
        
        # Assign min_value and max_value after they're calculated (whole numbers)
        representation['min_value'] = round(min_value) if min_value is not None else None
        representation['max_value'] = round(max_value) if max_value is not None else None
        
        representation['reading_batch_id'] = reading_batch_id
        representation.update(cluster_fields(supply_point))
        # Use pre-fetched batch readings
        batch_readings_by_meter = self.context.get('batch_readings_by_meter', {})
        batch_reading = batch_readings_by_meter.get(instance.id)
        
        if batch_reading:
            representation['new_reading'] = batch_reading.reading_value
            representation['new_reading_date'] = batch_reading.reading_date
            encoded_photo = self._encode_photo_to_base64(batch_reading.photo) if batch_reading.photo else None
            representation['new_photo'] = 'data:image/jpeg;base64,' + encoded_photo if encoded_photo else None
            representation['reader_alert'] = ReaderAlertSerializer(batch_reading.reader_alert).data if batch_reading.reader_alert else None
        else:
            representation['new_reading'] = None
            representation['new_reading_date'] = None
            representation['new_photo'] = None
            representation['reader_alert'] = None
        
        # For last reading, we still need to query as it's not in the batch
        if batch_reading:
            reading = Reading.objects.exclude(id=batch_reading.id).filter(meter=instance).order_by('-reading_date','-created_at').first()
        else:
            reading = Reading.objects.filter(meter=instance).order_by('-reading_date','-created_at').first()
        if reading:
            representation['last_reading'] = reading.reading_value
            representation['last_reading_date'] = reading.reading_date
            representation['last_reading_origin'] = reading.origin
            representation['last_reading_is_estimated'] = reading.is_estimated
            representation['previous_reading_id'] = reading.id
        else:
            representation['last_reading'] = None
            representation['previous_reading_id'] = None
        
        # Cache the serialized representation to avoid redundant serialization
        if cache is not None:
            cache[instance.id] = representation

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