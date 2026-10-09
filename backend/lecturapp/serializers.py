import base64
from rest_framework import serializers
from django.db.models import Count, Q

from billing.models import Reading, ReadingBatch
from billing.serializers.reading_batch_serializer import ReadingBatchStatusSerializer
from billing.serializers.reading_serializer import ReaderAlertSerializer
from billing.utils.reading_service import get_average_consumption
from coredata.models import ConfigProject
from service.models import Meter, Property, Route, RoutePosition
from service.serializers.route_serializer import RouteZoneSerializer
from statistics.models import ContractConsumption
from .models import ReadingOperator

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
                Q(positions__properties__supply_points__meter__status__token__isnull=False) &
                Q(positions__properties__supply_points__meter__has_remote_reading=True, positions__properties__supply_points__meter__force_manual_reading=False) & 
                ~Q(positions__properties__supply_points__meter__status__token__in=excluded_tokens)
            )
        elif obj.include_manual and not obj.include_telecontrol:
            main_filter = (
                Q(positions__properties__supply_points__meter__status__token__isnull=False) &
                ~Q(positions__properties__supply_points__meter__status__token__in=excluded_tokens) &
                ( Q(positions__properties__supply_points__meter__has_remote_reading=False) |
                    Q(positions__properties__supply_points__meter__force_manual_reading=True))
            )
        else:
            main_filter = (
                Q(positions__properties__supply_points__meter__status__token__isnull=False) &
                ~Q(positions__properties__supply_points__meter__status__token__in=excluded_tokens)
            )

        return obj.routes.aggregate(
            total=Count(
                'positions__properties',
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
            if obj.include_telecontrol and not obj.include_manual:
                main_meters = obj.routes.aggregate(
                    total=Count('positions__properties__supply_points__meter',
                            filter=(Q(positions__properties__supply_points__meter__status__token__isnull=False) & 
                                  Q(positions__properties__supply_points__meter__has_remote_reading=True, positions__properties__supply_points__meter__force_manual_reading=False) & 
                                    ~Q(positions__properties__supply_points__meter__status__token__in=[token_meter_status_no_meter, '-1'])),
                            distinct=True)
                )['total'] or 0
            elif obj.include_manual and not obj.include_telecontrol:
                main_meters = obj.routes.aggregate(
                    total=Count('positions__properties__supply_points__meter',
                            filter=(Q(positions__properties__supply_points__meter__status__token__isnull=False) & 
                                    ~Q(positions__properties__supply_points__meter__status__token__in=[token_meter_status_no_meter, '-1']) &
                                    (Q(positions__properties__supply_points__meter__has_remote_reading=False) | Q(positions__properties__supply_points__meter__force_manual_reading=True))),
                            distinct=True)
                )['total'] or 0
            else:
                main_meters = obj.routes.aggregate(
                    total=Count('positions__properties__supply_points__meter',
                            filter=(Q(positions__properties__supply_points__meter__status__token__isnull=False) &
                                    ~Q(positions__properties__supply_points__meter__status__token__in=[token_meter_status_no_meter, '-1'])),
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
            properties = obj.properties.filter(Q(supply_points__meter__has_remote_reading=False) | Q(supply_points__meter__force_manual_reading=True)).distinct()
        else:
            properties = obj.properties.all()
        
        return PropertyAppSerializer(properties, many=True, context=self.context).data

class RoutePositionAppDetailedSerializer(serializers.ModelSerializer):
    # read
    properties = serializers.SerializerMethodField()
    
    class Meta:
        model = RoutePosition
        fields = '__all__'
    
    def get_properties(self, obj):
        return PropertyAppDetailedSerializer(obj.properties.all(), many=True, context=self.context).data
    
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
                Q(properties__supply_points__meter__status__token__isnull=False) &
                Q(properties__supply_points__meter__has_remote_reading=True, properties__supply_points__meter__force_manual_reading=False) & 
                ~Q(properties__supply_points__meter__status__token__in=excluded_tokens)
            )
        else:
            main_filter = (
                Q(properties__supply_points__meter__status__token__isnull=False) &
                ~Q(properties__supply_points__meter__status__token__in=excluded_tokens) &
                (Q(properties__supply_points__meter__has_remote_reading=False) | Q(properties__supply_points__meter__force_manual_reading=True))
            )
        return obj.positions.aggregate(
            count=Count('properties',
                        filter=main_filter,
                        distinct=True)
        )['count'] or 0
    
    def get_num_meters(self, obj):
        # Calculate the number of unique meters using database aggregation (excluding meters with status token '-1')

        exclude_telecontrol = not self.context.get('include_telecontrol', False)
        token_meter_status_no_meter = ConfigProject.objects.get(token='token_meter_status_no_meter').value
        # Build the filter for main meters
        main_meter_filter = Q(properties__supply_points__meter__status__token__isnull=False) & ~Q(properties__supply_points__meter__status__token__in=[token_meter_status_no_meter,'-1'])
        if exclude_telecontrol:
            main_meter_filter &= (Q(properties__supply_points__meter__has_remote_reading=False) | Q(properties__supply_points__meter__force_manual_reading=True)) & ~Q(properties__supply_points__meter__status__token__in=[token_meter_status_no_meter,'-1'])
        else:
            main_meter_filter &= Q(properties__supply_points__meter__has_remote_reading=True, properties__supply_points__meter__force_manual_reading=False) & ~Q(properties__supply_points__meter__status__token__in=[token_meter_status_no_meter,'-1'])
        
        # Count main meters
        main_meters_count = obj.positions.aggregate(
            count=Count('properties__supply_points__meter', 
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
        exclude_telecontrol = not self.context.get('include_telecontrol', False)
        token_meter_status_no_meter = ConfigProject.objects.get(token='token_meter_status_no_meter').value
        if exclude_telecontrol:
            positions = obj.positions.filter(Q(properties__supply_points__meter__has_remote_reading=False) | Q(properties__supply_points__meter__force_manual_reading=True)).distinct()
        else:
            positions = obj.positions.distinct()

        # Prefetch to avoid N+1 when checking meter status
        positions = positions.prefetch_related(
            'properties__supply_points__meter__status'
        )
        positions_list = list(positions)

        def position_has_valid_meter(position):
            """True if at least one meter (main) has status != token_meter_status_no_meter."""
            for prop in position.properties.all():
                for sp in prop.supply_points.all():
                    if sp.meter:
                        if sp.meter.status and sp.meter.status.token != token_meter_status_no_meter:
                            return True
            return False

        positions_filtered = [p for p in positions_list if position_has_valid_meter(p)]
        return RoutePositionAppDetailedSerializer(positions_filtered, many=True, context=self.context).data
    
# PROPERTIES

class PropertyAppDetailedSerializer(serializers.ModelSerializer):
    meters = serializers.SerializerMethodField()
    class Meta:
        model = Property
        fields = '__all__'

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        reading_batch_id = self.context.get('reading_batch_id')
        batch_readings = self.context.get('batch_readings', [])
        token_meter_status_no_meter = ConfigProject.objects.get(token='token_meter_status_no_meter').value
        
        # Build a set of meter IDs from the instance (excluding meters with status token_meter_status_no_meter)
        meter_ids = set()
        exclude_telecontrol = not self.context.get('include_telecontrol', False)
        if exclude_telecontrol:
            supply_points = instance.supply_points.filter(Q(meter__has_remote_reading=False) | Q(meter__force_manual_reading=True)).distinct()
        else:
            supply_points = instance.supply_points.distinct()
        
        for supply_point in supply_points:
            if supply_point.meter:
                # Add main meter (only if status token is not token_meter_status_no_meter)
                if supply_point.meter.status and supply_point.meter.status.token != token_meter_status_no_meter:
                    meter_ids.add(supply_point.meter.id)

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
        # supply_points = obj.supply_points.all()
        meters = []
        # Use global seen_meter_ids from context if available (for progress tracking)
        global_seen = self.context.get('seen_meter_ids', set())
        local_seen_meter_ids = set()  # Track unique meter IDs in this property to avoid duplicates
        
        exclude_telecontrol = not self.context.get('include_telecontrol', False)
        token_meter_status_no_meter = ConfigProject.objects.get(token='token_meter_status_no_meter').value
        
        if exclude_telecontrol:
            supply_points = obj.supply_points.filter(Q(meter__has_remote_reading=False) | Q(meter__force_manual_reading=True)).distinct()
        else:
            supply_points = obj.supply_points.distinct()
        
        for supply_point in supply_points:
            if supply_point.meter:
                # Add main meter if not seen in this property and status is not no_meter
                if (supply_point.meter.id not in local_seen_meter_ids and
                    supply_point.meter.status and supply_point.meter.status.token != token_meter_status_no_meter):
                    meters.append(supply_point.meter)
                    local_seen_meter_ids.add(supply_point.meter.id)
        
        
        return MeterAppSerializer(meters, many=True, context=self.context).data


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
        
        if exclude_telecontrol:
            supply_points = instance.supply_points.filter(Q(meter__has_remote_reading=False) | Q(meter__force_manual_reading=True)).distinct()
        else:
            supply_points = instance.supply_points.distinct()
        
        # Count supply points and readings using pre-fetched data (excluding meters with status token '-1')
        for supply_point in supply_points:
            if supply_point.meter:
                # Only count meter if status token is not '-1'
                if supply_point.meter.status and supply_point.meter.status.token != '-1':
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
        representation['has_cluster'] = True if supply_point and supply_point.cluster_nozzle and supply_point.cluster_nozzle.cluster else False
        if representation['has_cluster']:
            representation['cluster_nozzle_col'] = supply_point.cluster_nozzle.col if supply_point.cluster_nozzle.col else supply_point.cluster_nozzle.position
            representation['cluster_nozzle_row'] = supply_point.cluster_nozzle.row if supply_point.cluster_nozzle.row else 1
            representation['cluster_position'] = supply_point.cluster_nozzle.position if supply_point.cluster_nozzle.position else 1
            representation['cluster_token'] = supply_point.cluster_nozzle.cluster.token if supply_point.cluster_nozzle.cluster else None
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