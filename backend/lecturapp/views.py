import random
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from django.shortcuts import get_object_or_404
from django.contrib.auth.hashers import make_password
from django.http import JsonResponse
from django.db.models import Count, Q, Prefetch, Case, When, Value
from celery.result import AsyncResult
import json
import base64
from datetime import datetime
from django.core.files.base import ContentFile
from io import BytesIO

from billing.models import ReaderAlert, ReadingBatch, Reading
from contract.models import Contract
from coredata.models import ConfigProject
from service.models import Meter, SupplyPoint, SupplyPointPlacement
from .serializers import RouteAppSerializer, ReadingBatchAppSerializer
from .tasks import process_reading_batch_routes_detailed

from .models import ReadingOperator, Token
from .utils.sync_readings_service import process_sync_reading_row
from .serializers import (
    ReadingOperatorSerializer,
    ReadingOperatorCreateSerializer,
    ReadingOperatorUpdateSerializer,
    ReadingOperatorPasswordChangeSerializer,
    AuthenticationSerializer
)
from .decorators import lecturapp_auth_required, get_authenticated_operator

class ReadingOperatorViewSet(ModelViewSet):
    """
    ViewSet for ReadingOperator CRUD operations
    All endpoints require custom authentication
    """
    queryset = ReadingOperator.objects.all()
    serializer_class = ReadingOperatorSerializer
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ReadingOperatorCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ReadingOperatorUpdateSerializer
        return ReadingOperatorSerializer
    
    @lecturapp_auth_required
    def list(self, request, *args, **kwargs):
        """List all reading operators"""
        operators = self.get_queryset()
        serializer = self.get_serializer(operators, many=True)
        return JsonResponse(serializer.data, safe=False)
    
    @lecturapp_auth_required
    def retrieve(self, request, *args, **kwargs):
        """Get a specific reading operator"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return JsonResponse(serializer.data)
    
    @lecturapp_auth_required
    def create(self, request, *args, **kwargs):
        """Create a new reading operator"""
        serializer = self.get_serializer(data=request.POST)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse(serializer.data, status=201)
        return JsonResponse(serializer.errors, status=400)
    
    @lecturapp_auth_required
    def update(self, request, *args, **kwargs):
        """Update a reading operator"""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.POST, partial=True)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse(serializer.data)
        return JsonResponse(serializer.errors, status=400)
    
    @lecturapp_auth_required
    def destroy(self, request, *args, **kwargs):
        """Delete a reading operator"""
        instance = self.get_object()
        instance.delete()
        return JsonResponse({'message': 'Operator deleted successfully'})

class AuthenticationView(APIView):
    """
    Authentication endpoint for ReadingOperator
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Authenticate a reading operator and return a token"""
        serializer = AuthenticationSerializer(data=request.data)
        if serializer.is_valid():
            username = serializer.validated_data['username']
            password = serializer.validated_data['password']
            
            print(f"Authenticating operator with username: {username}")
            print(f"Password: {password}")
            operator = ReadingOperator.authenticate(username, password)
            if operator:
                # Generate a new token for this operator
                token = operator.generate_token()
                operator_serializer = ReadingOperatorSerializer(operator)
                return Response({
                    'success': True,
                    'message': 'Authentication successful',
                    'token': token.token,
                    'operator': operator_serializer.data
                })
            else:
                return Response({
                    'success': False,
                    'message': 'Invalid credentials'
                }, status=status.HTTP_401_UNAUTHORIZED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@lecturapp_auth_required
def password_change(request):
    """Change password for authenticated operator"""
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Only POST method is allowed'
        }, status=400)
    
    operator = get_authenticated_operator(request)
    serializer = ReadingOperatorPasswordChangeSerializer(data=request.POST)
    
    if serializer.is_valid():
        old_password = serializer.validated_data['old_password']
        new_password = serializer.validated_data['new_password']
        
        # Verify old password
        if not operator.check_password(old_password):
            return JsonResponse({
                'success': False,
                'message': 'Current password is incorrect'
            }, status=400)
        
        # Change password
        operator.set_password(new_password)
        
        return JsonResponse({
            'success': True,
            'message': 'Password changed successfully'
        })
    
    return JsonResponse(serializer.errors, status=400)

@lecturapp_auth_required
def operator_profile(request):
    """Get current operator profile"""
    operator = get_authenticated_operator(request)
    serializer = ReadingOperatorSerializer(operator)
    return JsonResponse(serializer.data)

@lecturapp_auth_required
def operator_logout(request):
    """Logout endpoint - invalidates the current token"""
    operator = get_authenticated_operator(request)
    if operator:
        # Delete all tokens for this operator
        Token.objects.filter(operator=operator).delete()
    
    return JsonResponse({
        'success': True,
        'message': 'Logged out successfully'
    })

@api_view(['GET'])
@permission_classes([AllowAny])
def validate_token(request):
    """Validate a token and return operator info"""
    token = request.GET.get('token') or request.headers.get('X-App-Token')
    
    print(f"Token: {token}")
    
    if not token:
        return Response({
            'success': False,
            'message': 'Token is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    operator = Token.get_operator_from_token(token)
    if operator and operator.is_active:
        operator_serializer = ReadingOperatorSerializer(operator)
        return Response({
            'success': True,
            'message': 'Token is valid',
            'operator': operator_serializer.data
        })
    else:
        return Response({
            'success': False,
            'message': 'Invalid or expired token'
        }, status=status.HTTP_401_UNAUTHORIZED)

@lecturapp_auth_required
def reading_batches(request):
    """Get all reading batches - OPTIMIZED"""

    batch_status_finish_token = ConfigProject.objects.get(token='batch_status_finish_token').value
    batch_status_cancel_token = ConfigProject.objects.get(token='batch_status_cancel_token').value
    batch_status_billed_token = ConfigProject.objects.get(token='batch_status_billed_token').value
    
    # Simple queryset - counts are calculated in the serializer to avoid expensive annotations
    reading_batches = ReadingBatch.objects.exclude(
        status__token__in=[batch_status_finish_token, batch_status_cancel_token, batch_status_billed_token]
    ).select_related('status').prefetch_related('routes', 'readings').order_by('-created_at')[:20]
    
    serializer = ReadingBatchAppSerializer(reading_batches, many=True)
    data = serializer.data

    return JsonResponse(data, safe=False)

@lecturapp_auth_required
def reading_batch_routes(request, reading_batch_id):
    """Get all reading batches - OPTIMIZED"""
    
    # Use select_related and prefetch_related to optimize query
    reading_batch = get_object_or_404(
        ReadingBatch.objects.prefetch_related(
            'routes__positions__properties__supply_points__meter',
            'routes__positions__properties__supply_points__contracts',
            'routes__positions__properties__supply_points__address',
            'routes__positions__properties__supply_points__placement',
            'routes__positions__properties__supply_points__cluster_nozzle__cluster',
            'fix_meters'
        ).select_related('status'),
        id=reading_batch_id
    )
    
    routes = reading_batch.routes.all()
    
    num_fix_meters = reading_batch.fix_meters.count()
    
    if not routes and num_fix_meters > 0:
        num_properties = reading_batch.fix_meters.aggregate(
                total=Count('supply_points__property', distinct=True)
            )['total'] or 0
        positions = []
        
        idx = 0
        
        for meter in reading_batch.fix_meters.all():
            
            sp = meter.supply_points.first()
            property = sp.property
            position = property.route_position
            
            # Check if position already exists
            existing_position = next((p for p in positions if p['id'] == position.id), None)
            
            if existing_position:
                # Position exists, increment num_meters
                # Check if property already exists in this position
                existing_property = next((prop for prop in existing_position['properties'] if prop['id'] == property.id), None)
                
                if existing_property:
                    # Property exists, increment num_meters
                    existing_property['num_meters'] += 1
                else:
                    # Property doesn't exist, add it
                    existing_position['properties'].append({
                        'id': property.id,
                        'name': property.name,
                        'address_complete': str(property.address_street) + ' ' + str(property.address_street_number),
                        'num_meters': 1,
                        'num_readings': 0,
                        'latitude': property.latitude,
                        'longitude': property.longitude,
                        'reading_observation': position.reader_observation
                    })
                    idx += 1
            else:
                # Position doesn't exist, add new position
                positions.append({
                    'id': position.id,
                    'token': position.token,
                    'position': position.position,
                    'reader_observation': position.reader_observation,
                    'notebook': position.notebook,
                    'properties': [
                        {
                            'id': property.id,
                            'name': property.name,
                            'address_complete': str(property.address_street) + ' ' + str(property.address_street_number),
                            'num_meters': 1,
                            'num_readings': 0,
                            'latitude': property.latitude,
                            'longitude': property.longitude,
                            'reading_observation': position.reader_observation
                        }
                    ]
                })
                idx += 1
            
            if idx >= 5:
                break
        
        data = {
            'id': random.randint(100000, 999999),
            'name': 'Ruta correctiva',
            'positions': positions,
            'num_properties': num_properties,
            'num_meters': reading_batch.fix_meters.count(),
        }
        data = [data]
    else:
        serializer = RouteAppSerializer(routes, many=True, context={'reading_batch_id': reading_batch_id, 'include_telecontrol': reading_batch.include_telecontrol})
        data = serializer.data
    return JsonResponse(data, safe=False)

@lecturapp_auth_required
def reading_batch_routes_detailed(request, reading_batch_id):
    """Get all reading batches with detailed information - ASYNC WITH CELERY & PROGRESS"""
    
    # Start the Celery task
    task = process_reading_batch_routes_detailed.delay(reading_batch_id)
    
    return JsonResponse({
        'status': 'processing',
        'message': 'Data processing started.',
        'task_id': task.id
    }, status=202)

@lecturapp_auth_required  
def reading_batch_routes_detailed_status(request, task_id):
    """Check the status and progress of reading batch routes detailed processing"""
    
    try:
        task = AsyncResult(task_id)
        
        if task.state == 'PENDING':
            return JsonResponse({
                'status': 'pending',
                'message': 'Task is waiting to be processed',
                'progress': {
                    'current': 0,
                    'total': 100,
                    'description': 'Waiting in queue...'
                }
            })
        elif task.state == 'PROGRESS':
            # Get progress info from celery-progress
            progress_info = task.info
            return JsonResponse({
                'status': 'processing',
                'message': 'Task is being processed',
                'progress': {
                    'current': progress_info.get('current', 0),
                    'total': progress_info.get('total', 100),
                    'description': progress_info.get('description', 'Processing...')
                }
            })
        elif task.state == 'SUCCESS':
            result = task.result
            if result.get('status') == 'completed':
                return JsonResponse({
                    'status': 'completed',
                    'message': result.get('message', 'Processing completed successfully'),
                    'data': result.get('data'),
                    'progress': {
                        'current': 100,
                        'total': 100,
                        'description': 'downloading...'
                    }
                })
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': result.get('message', 'Unknown error occurred'),
                    'progress': {
                        'current': 0,
                        'total': 100,
                        'description': 'Error occurred'
                    }
                }, status=500)
        elif task.state == 'FAILURE':
            return JsonResponse({
                'status': 'error',
                'message': str(task.info),
                'progress': {
                    'current': 0,
                    'total': 100,
                    'description': 'Task failed'
                }
            }, status=500)
        else:
            return JsonResponse({
                'status': 'unknown',
                'message': f'Unknown task state: {task.state}',
                'progress': {
                    'current': 0,
                    'total': 100,
                    'description': 'Unknown state'
                }
            }, status=500)
            
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error checking task status: {str(e)}',
            'progress': {
                'current': 0,
                'total': 100,
                'description': 'Error checking status'
            }
        }, status=500)

@lecturapp_auth_required
def sync_readings(request, reading_batch_id):
    """Sync reading app data to server"""
    
    reading_batch = get_object_or_404(ReadingBatch, id=reading_batch_id)
    
    operator = get_authenticated_operator(request)
    print(f"Operator: {operator}")
    print(f"Reading batch: {reading_batch}")
    
    contract_active_token = ConfigProject.objects.get(token='contract_active_token').value
    meter_ids = []
    
    # Parse the request body as JSON
    try:
        data = json.loads(request.body)
        readings = data.get('readings', [])
        # print(f"Readings data: {readings}")
        
        if readings:
            for r in readings:
                print(f"-----------------------------------------")
                print(f"Reading Meter: {r.get('id')} - {r.get('code')}")
                print(f"Fields to update: {(r.get('changes_to_save') or '').split(',')}")

                action, meter_id, message = process_sync_reading_row(
                    r,
                    reading_batch,
                    operator,
                    contract_active_token,
                    dry_run=False,
                )
                print(message)
                if meter_id:
                    meter_ids.append(meter_id)
        
    except (json.JSONDecodeError, AttributeError) as e:
        print(f"Error parsing request body: {e}")
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON data'
        }, status=400)
    
    # Count processed readings
    processed_count = 0
    if readings:
        processed_count = len(readings)
    
    return JsonResponse({
        'success': True,
        'message': 'Readings synced successfully',
        'readings_count': processed_count,
        'batch_id': reading_batch_id,
        'operator_id': operator.id if operator else None,
        'meter_ids': meter_ids
    })
    