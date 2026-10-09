import random
from celery import shared_task
from celery_progress.backend import ProgressRecorder
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch, Q, Count

from billing.models import ReadingBatch, Reading
from service.models import SupplyPoint
from coredata.models import ConfigProject
from .serializers import RouteAppDetailSerializer, MeterAppSerializer


@shared_task(bind=True)
def process_reading_batch_routes_detailed(self, reading_batch_id):
    """
    Process reading batch routes detailed data in background with progress tracking
    """
    progress_recorder = ProgressRecorder(self)
    
    try:
        progress_recorder.set_progress(0, 100, "Starting data processing...")
        
        reading_batch = get_object_or_404(ReadingBatch, id=reading_batch_id)
        activate_token = ConfigProject.objects.get(token='supply_point_status_activate_token').value
        token_meter_status_no_meter = ConfigProject.objects.get(token='token_meter_status_no_meter').value
        
        progress_recorder.set_progress(5, 100, "Fetching routes and optimizing queries...")
        
        exclude_telecontrol = not reading_batch.include_telecontrol
        
        # Check if routes exist
        routes = reading_batch.routes.all()
        num_fix_meters = reading_batch.fix_meters.count()
        
        # Pre-fetch batch readings to avoid N+1 queries
        progress_recorder.set_progress(10, 100, "Fetching batch readings...")
        
        if exclude_telecontrol:
            batch_readings = Reading.objects.filter(batch=reading_batch_id).filter(
                Q(meter__has_remote_reading=False) | Q(meter__force_manual_reading=True)
                ).exclude(meter__sub_meters__status__token=token_meter_status_no_meter).select_related(
                'meter', 'reader_alert'
            )
        else:
            batch_readings = Reading.objects.filter(batch=reading_batch_id).exclude(meter__sub_meters__status__token=token_meter_status_no_meter).select_related(
                'meter', 'reader_alert'
            )
        
        # Handle fix_meters case (when no routes exist)
        if not routes and num_fix_meters > 0:
            progress_recorder.set_progress(15, 100, "Processing fix meters...")
            
            # Prefetch fix_meters with related data (no sub_meters)
            fix_meters = reading_batch.fix_meters.prefetch_related(
                'supply_points__property__route_position',
                Prefetch(
                    'supply_points__property__supply_points',
                    queryset=SupplyPoint.objects.filter(status__token=activate_token).select_related(
                        'meter', 'status', 'address', 'placement', 'cluster_nozzle__cluster'
                    ).prefetch_related(
                        'contracts',
                        'meter__supply_points__contracts__holder',
                        'meter__supply_points__address',
                        'meter__supply_points__placement',
                        'meter__supply_points__cluster_nozzle',
                        'meter__supply_points__cluster_nozzle__cluster',
                    )
                ),
            )
            
            # Count distinct properties
            num_properties = reading_batch.fix_meters.aggregate(
                total=Count('supply_points__property', distinct=True)
            )['total'] or 0
            
            # Total meters is simply the count of fix_meters
            total_meters = num_fix_meters
            
            # Create context for serialization with progress tracking
            context = {
                'reading_batch_id': reading_batch_id,
                'batch_readings': batch_readings,
                'batch_readings_by_meter': {reading.meter_id: reading for reading in batch_readings if reading.meter_id},
                'exclude_telecontrol': exclude_telecontrol,
                'total_meters': total_meters,
                'month': reading_batch.created_at.month,
                'include_telecontrol': reading_batch.include_telecontrol,
                'progress_recorder': progress_recorder,
                'seen_meter_ids': set(),
                'serialized_meters_cache': {}
            }
            
            progress_recorder.set_progress(20, 100, "Building positions from fix meters...")
            
            # Build positions dictionary to avoid duplicates
            # Key: position_id, Value: position data with properties
            # For each property, track which meters from fix_meters belong to it
            positions_dict = {}
            # Track meters per property: {property_id: [meter1, meter2, ...]}
            property_meters = {}
            
            # First pass: collect meters per property (only main meters, no sub_meters)
            for meter in fix_meters:
                sp = meter.supply_points.first()
                if not sp or not sp.property:
                    continue
                
                property_obj = sp.property
                if property_obj.id not in property_meters:
                    property_meters[property_obj.id] = []
                
                # Add main meter if status is valid (ignore sub_meters)
                if meter.status and meter.status.token != '-1':
                    if (not exclude_telecontrol) or (exclude_telecontrol and (not getattr(meter, 'has_remote_reading', False) or getattr(meter, 'force_manual_reading', False))):
                        property_meters[property_obj.id].append(meter)
            
            # Second pass: build positions and properties with only fix_meters
            for meter in fix_meters:
                sp = meter.supply_points.first()
                if not sp or not sp.property:
                    continue
                
                property_obj = sp.property
                position = property_obj.route_position
                
                if not position:
                    continue
                
                # Check if position already exists
                if position.id not in positions_dict:
                    # Create position base data
                    positions_dict[position.id] = {
                        'id': position.id,
                        'token': position.token,
                        'position': position.position,
                        'reader_observation': position.reader_observation,
                        'notebook': position.notebook,
                        'properties': []
                    }
                
                # Check if property already exists in this position
                existing_property = next((prop for prop in positions_dict[position.id]['properties'] if prop['id'] == property_obj.id), None)
                
                if not existing_property:
                    # Get meters for this property (only from fix_meters)
                    meters_for_property = property_meters.get(property_obj.id, [])
                    
                    # Build property data manually
                    property_data = {
                        'id': property_obj.id,
                        'created_at': property_obj.created_at.isoformat() if property_obj.created_at else None,
                        'updated_at': property_obj.updated_at.isoformat() if property_obj.updated_at else None,
                        'token': property_obj.token,
                        'name': property_obj.name,
                        'cadastral': property_obj.cadastral,
                        'is_active': property_obj.is_active,
                        'latitude': property_obj.latitude if property_obj.latitude else 0,
                        'longitude': property_obj.longitude if property_obj.longitude else 0,
                        'address_complete': str(property_obj.address_street) + ' ' + str(property_obj.address_street_number),
                        'num_meters': len(meters_for_property),
                        'num_readings': sum(1 for reading in batch_readings if reading.meter_id in [m.id for m in meters_for_property]),
                        'route_position': position.id if position else None,
                        'address_street': property_obj.address_street_id,
                        'address_street_number': property_obj.address_street_number_id,
                        'address_postal_code': property_obj.address_postal_code_id,
                        'address_city': property_obj.address_city_id,
                        'reading_observation': position.reader_observation if position else None,
                    }
                    
                    # Serialize only the meters from fix_meters for this property
                    if meters_for_property:
                        meter_serializer = MeterAppSerializer(meters_for_property, many=True, context=context)
                        property_data['meters'] = meter_serializer.data
                    else:
                        property_data['meters'] = []
                    
                    positions_dict[position.id]['properties'].append(property_data)
            
            # Convert positions dict to list
            final_positions = list(positions_dict.values())
            
            progress_recorder.set_progress(95, 100, "Finalizing data...")
            
            id = random.randint(100000, 999999)
            
            # Build the route data structure
            serialized_data = [{
                'id': id,
                'token': f'CR-{id}',
                'name': 'Ruta correctiva',
                'positions': final_positions,
                'num_properties': num_properties,
                'num_meters': reading_batch.fix_meters.count(),
            }]
            
            progress_recorder.set_progress(100, 100, "Processing completed")
            
            return {
                'status': 'completed',
                'data': serialized_data,
                'message': f'Successfully processed fix meters route with {len(final_positions)} positions'
            }
        
        # Original routes case
        # Optimize queries with prefetch_related and select_related (only active supply points)
        
        # REMOVED FILTER BY ACTIVE STATUS
        routes = routes.prefetch_related(
            'route_zone',
            Prefetch(
                'positions__properties__supply_points',
                queryset=SupplyPoint.objects.all().select_related(
                    'meter', 'status', 'address', 'placement', 'cluster_nozzle__cluster'
                ).prefetch_related(
                    'meter__sub_meters',
                    'contracts',
                    'meter__supply_points__contracts__holder',
                    'meter__supply_points__address',
                    'meter__supply_points__placement',
                    'meter__supply_points__cluster_nozzle',
                    'meter__supply_points__cluster_nozzle__cluster',
                )
            ),
        ).select_related(
            'route_zone'
        )
        
        progress_recorder.set_progress(20, 100, "Preparing data context...")
        
        # Build a global distinct set of meters to avoid double-counting across routes/positions
        distinct_meter_ids = set()
        
        for route in routes:
            # Use prefetched positions -> properties -> supply_points -> meter (+ sub_meters)
            for position in route.positions.all():
                for prop in position.properties.all():
                    for sp in prop.supply_points.all():
                        meter = getattr(sp, 'meter', None)
                        if not meter:
                            continue
                        # Main meter filters
                        if getattr(meter, 'status', None) and getattr(meter.status, 'token', None) != '-1' and getattr(meter.status, 'token', None) != token_meter_status_no_meter:
                            if (not exclude_telecontrol) or (exclude_telecontrol and (not getattr(meter, 'has_remote_reading', False) or getattr(meter, 'force_manual_reading', False))):
                                distinct_meter_ids.add(meter.id)
                        # Sub-meters
                        if hasattr(meter, 'sub_meters'):
                            for sub_meter in meter.sub_meters.all():
                                if getattr(sub_meter, 'status', None) and getattr(sub_meter.status, 'token', None) != '-1' and getattr(sub_meter.status, 'token', None) != token_meter_status_no_meter:
                                    if (not exclude_telecontrol) or (exclude_telecontrol and (not getattr(sub_meter, 'has_remote_reading', False) or getattr(sub_meter, 'force_manual_reading', False))):
                                        distinct_meter_ids.add(sub_meter.id)
        
        total_meters = len(distinct_meter_ids)
        
        # Create a context with pre-fetched data
        context = {
            'reading_batch_id': reading_batch_id,
            'batch_readings': batch_readings,
            'batch_readings_by_meter': {reading.meter_id: reading for reading in batch_readings if reading.meter_id},
            'exclude_telecontrol': exclude_telecontrol,
            'include_telecontrol': reading_batch.include_telecontrol,
            'total_meters': total_meters,
            'month': reading_batch.created_at.month
        }
        
        progress_recorder.set_progress(30, 100, "Serializing data...")
        
        context["progress_recorder"] = progress_recorder
        # Track which meters have already been serialized to avoid over-incrementing progress
        context["seen_meter_ids"] = set()
        # Cache of serialized meters to avoid redundant serialization
        context["serialized_meters_cache"] = {}
        
        serializer = RouteAppDetailSerializer(routes, many=True, context=context)
        serialized_data = serializer.data
        
        progress_recorder.set_progress(100, 100, "Processing completed")
        
        return {
            'status': 'completed',
            'data': serialized_data,
            'message': f'Successfully processed {len(serialized_data)} routes'
        }
        
    except Exception as e:
        progress_recorder.set_progress(0, 100, f"Error: {str(e)}")
        
        return {
            'status': 'error',
            'message': str(e)
        } 