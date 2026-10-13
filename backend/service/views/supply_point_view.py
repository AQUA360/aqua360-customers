# services/views/supply_point_view.py

import datetime
from rest_framework.decorators import action
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from django.db.models import Prefetch, F, CharField, Value, Exists, OuterRef, Q
from django.db.models.functions import Concat

from auth.permissions import PermissionManager
from billing.models import EstimatedBagMovement, Reading
from service.models import Meter, MeterStatus, SupplyCut, SupplyPoint, SupplyPointObservation, Property
from service.serializers.supply_point_serializer import SupplyPointListSerializer, SupplyPointSerializer
from service.filters.supply_point_filter import SupplyPointFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..utils.supply_point_service import supply_point_activate, supply_point_change_address, supply_point_change_meter, supply_point_deactivate, supply_point_change_property
from fraud.models import Fraud, FraudStatus
from coredata.models import ConfigProject
from service.permissions import SupplyPointPermission
from contract.permissions import ContractPermission, ContractRequestPermission
from fraud.permissions import FraudPermission
class SupplyPointViewSet(viewsets.ModelViewSet):
    serializer_class = SupplyPointSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filterset_class = SupplyPointFilter
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ['token', 'address_complete', 'address_city', 'status_name', 'type_name',
                       'property_route_position_token', 'meter_code', 'cluster_nozzle_token',
                       'connection_token', 'connection_exploitation_name', 'placement_name']

    def get_queryset(self):
        return SupplyPoint.objects.select_related(
            'type',
            'status',
            'property__route_position',
            'meter',
            'cluster_nozzle',
            'connection__exploitation',
            'address__street',
            'address__country'
        ).prefetch_related(
            'supply_point_children',
            'contracts__holder',
            'contracts__status',
            Prefetch(
                'supply_cuts',
                queryset=SupplyCut.objects.select_related('status', 'cause').order_by('-id'),
                to_attr='_prefetched_supply_cuts',
            )
        ).annotate(
            current_fraud=Exists(
                Fraud.objects.filter(
                    supply_point=OuterRef('pk'),
                    status__token__in=[
                        ConfigProject.objects.get(token="fraud_status_pending_token").value,
                        ConfigProject.objects.get(token="fraud_status_active_token").value
                    ]
                )
            ),
            previous_fraud=Exists(
                Fraud.objects.filter(
                    supply_point=OuterRef('pk'),
                    status__token__in=[
                        ConfigProject.objects.get(token="fraud_status_resolved_token").value,
                        ConfigProject.objects.get(token="fraud_status_expired_token").value
                    ]
                )
            )
        ).order_by('token')

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = SupplyPointSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data)
        
    def get_queryset(self):
        queryset = SupplyPoint.objects.select_related(
            'type',
            'status',
            'property__route_position',
            'meter',
            'cluster_nozzle',
            'connection__exploitation',
            'address__street',
            'address__country',
            'placement',
        ).prefetch_related(
            'supply_point_children',
            'contracts__holder',
            'contracts__status',
            Prefetch(
                'supply_cuts',
                queryset=SupplyCut.objects.select_related('status', 'cause').order_by('-id'),
                to_attr='_prefetched_supply_cuts',
            )
        ).annotate(
            current_fraud=Exists(
                Fraud.objects.filter(
                    supply_point=OuterRef('pk'),
                    status__token__in=[
                        ConfigProject.objects.get(token="fraud_status_pending_token").value,
                        ConfigProject.objects.get(token="fraud_status_active_token").value
                    ]
                )
            ),
            previous_fraud=Exists(
                Fraud.objects.filter(
                    supply_point=OuterRef('pk'),
                    status__token__in=[
                        ConfigProject.objects.get(token="fraud_status_resolved_token").value,
                        ConfigProject.objects.get(token="fraud_status_expired_token").value
                    ]
                )
            )
        ).order_by('token')

        queryset = queryset.annotate(
            type_name=F('type__name'),
            status_name=F('status__name'),
            cluster_nozzle_token=F('cluster_nozzle__token'),
            meter_code=F('meter__code'),
            connection_token=F('connection__token'),
            connection_exploitation_name=F('connection__exploitation__name'),
            property_route_position_token=F('property__route_position__token'),
            address_complete=F('address__address_search'),
            address_city=F('address__city__name'),
            placement_name=F('placement__name'),
        ).prefetch_related(
            Prefetch('observations', queryset=SupplyPointObservation.objects.order_by('-created_at'))
        )
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':  # Corresponds to GET / (list view)
            return SupplyPointListSerializer
        return super().get_serializer_class()

    @action(detail=False, methods=['get'], url_path='list')
    def simple_list(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        paginator = PageNumberPagination()
        paginator.page_size = 50
        result_page = paginator.paginate_queryset(queryset, request)
        serializer = SupplyPointListSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)
    
    
    @action(detail=False, methods=['post'], url_path='update-meter')
    def update_meter(self, request):
        supplypoint_permissions = PermissionManager.get_model_permissions(request.user, 'supplypoint', 'service')
        contract_permissions = PermissionManager.get_model_permissions(request.user, 'contract', 'contract')
        contractrequest_permissions = PermissionManager.get_model_permissions(request.user, 'contractrequest', 'contract')
        fraud_permissions = PermissionManager.get_model_permissions(request.user, 'fraud', 'fraud')
        
        if not any([
            supplypoint_permissions['can_change'],
            contract_permissions['can_change'],
            contractrequest_permissions['can_change'],
            fraud_permissions['can_change']
        ]):
            return Response({"error": "Insufficient permissions to update meter"}, status=status.HTTP_403_FORBIDDEN)
        
        supply_point_id = request.data.get('supply_point_id')
        meter_id = request.data.get('meter_id')
        if not supply_point_id or not meter_id:
            return Response({"error": "supply_point_id and meter_id are required"}, status=status.HTTP_400_BAD_REQUEST)
        meter = Meter.objects.get(id=meter_id)
        if not meter.is_general:
            supply_points_meter = SupplyPoint.objects.filter(meter=meter)
            supply_points_meter.update(meter=None)
        supply_point = SupplyPoint.objects.get(id=supply_point_id)
        previous_meter = supply_point.meter
        supply_point.meter = meter
        supply_point.save()
        
        supply_point_change_meter(request.user, supply_point.id, previous_meter, meter)
        serializer = SupplyPointSerializer(supply_point, context={'request': request})
        return Response(serializer.data)
    
    
    @action(detail=False, methods=['post'], url_path='save-meter-change')
    def save_meter_change(self, request):
        supplypoint_permissions = PermissionManager.get_model_permissions(request.user, 'supplypoint', 'service')
        contract_permissions = PermissionManager.get_model_permissions(request.user, 'contract', 'contract')
        
        if not any([
            supplypoint_permissions['can_change'],
            contract_permissions['can_change'],
        ]):
            return Response({"error": "Insufficient permissions to update meter"}, status=status.HTTP_403_FORBIDDEN)
        
        supply_point_id = request.data.get('supply_point')
        prev_meter_id = request.data.get('prev_meter')
        new_meter_id = request.data.get('new_meter')
        origin = request.data.get('origin')
        
        change_date = request.data.get('change_date')
        try:
            change_date_instance = datetime.datetime.strptime(change_date, '%Y-%m-%d').date()
        except:
            change_date_instance = change_date
        previous_reading_data = request.data.get('previous_reading')
        new_reading_data = request.data.get('new_reading')
        
        if not supply_point_id or not new_meter_id:
            return Response({"error": "supply_point_id and meter_id are required"}, status=status.HTTP_400_BAD_REQUEST)
        
        current_meter = Meter.objects.get(id=prev_meter_id) if prev_meter_id else None
        new_meter = Meter.objects.get(id=new_meter_id)
        
        active_contract_token = ConfigProject.objects.get(token='contract_active_token').value
        meter_status_active_token = ConfigProject.objects.get(token='meter_status_active_token').value
        meter_status_inactive_token = ConfigProject.objects.get(token='meter_status_inactive_token').value
        meter_status_active = MeterStatus.objects.get(token=meter_status_active_token)
        meter_status_inactive = MeterStatus.objects.get(token=meter_status_inactive_token)
        
        
        if not new_meter.is_general:
            supply_points_meter = SupplyPoint.objects.filter(meter=new_meter)
            supply_points_meter.update(meter=None)
        supply_point = SupplyPoint.objects.get(id=supply_point_id)
        supply_point.meter = new_meter
        supply_point.save()
        
        if new_meter.status.token != meter_status_active_token:
            new_meter.status = meter_status_active
            new_meter.save()
        
        if current_meter:
            current_meter_supply_points = SupplyPoint.objects.filter(meter=current_meter)
            if current_meter_supply_points.count() == 0:
                current_meter.status = meter_status_inactive
                current_meter.save()
        
        supply_point_change_meter(request.user, supply_point.id, current_meter, new_meter)
        
        previous_reading_instance = Reading.objects.filter(meter=current_meter, is_control=False).order_by('-reading_date').first() if current_meter else None
        
        def _create_meter_reading(meter, reading_data, date, supply_point, previous_reading, active_contract_token):
            supply_point_contracts = supply_point.contracts.filter(status__token=active_contract_token)
            for contract in supply_point_contracts:
                contract_prev_reading = Reading.objects.filter(
                    contract=contract,
                    supply_point=supply_point,
                    is_control=False,
                    reading_date__lte=date,
                ).order_by('-reading_date').first()
                
                try:
                    estimated_bag = contract.estimated_bags.filter(supply_point=supply_point).first()
                except:
                    estimated_bag = None
                
                calculated_value = int(reading_data.get('calculated_value'))
                consumption_days = (date - contract_prev_reading.reading_date).days if contract_prev_reading else 0
                if (
                    contract_prev_reading
                    and contract_prev_reading.invoices.count() == 0
                    and contract_prev_reading.previous_reading
                    and not contract_prev_reading.is_control
                    and not contract_prev_reading.is_close
                    and not contract_prev_reading.previous_reading.is_close
                    ):
                    calculated_value = int(contract_prev_reading.calculated_value) + int(calculated_value)
                    consumption_days = int(consumption_days or 0) + int(contract_prev_reading.consumption_days or 0)
                    contract_prev_reading.is_control = True
                    contract_prev_reading.save()
                    contract_prev_reading = contract_prev_reading.previous_reading
                
                used_estimated = None
                if estimated_bag and estimated_bag.total_consumption > 0:
                    used_estimated = estimated_bag.total_consumption if estimated_bag.total_consumption < calculated_value else calculated_value
                    
                    
                reading = Reading.objects.create(
                    supply_point=supply_point,
                    contract=contract,
                    meter=meter,
                    reading_date=date,
                    reading_value=reading_data.get('reading_value'),
                    calculated_value=calculated_value,
                    consumption_days=consumption_days,
                    is_close=reading_data.get('is_close'),
                    origin=origin,
                    leak_value=reading_data.get('leak_value'),
                    real_consumption=int(calculated_value) - int(used_estimated or 0), 
                    estimated_used=used_estimated,
                    previous_reading=contract_prev_reading,
                )
                
                if used_estimated and used_estimated > 0:
                    EstimatedBagMovement.objects.create(
                        amount=used_estimated,
                        estimated_bag=estimated_bag,
                        reading=reading,
                        movement_date=date,
                        is_positive=False
                    )
                    estimated_bag.total_consumption -= used_estimated
                    estimated_bag.save()
                
        if current_meter:
            _create_meter_reading(current_meter, previous_reading_data, change_date_instance, supply_point, previous_reading_instance, active_contract_token)
        
        _create_meter_reading(new_meter, new_reading_data, change_date_instance, supply_point, None, active_contract_token)
        
        serializer = SupplyPointSerializer(supply_point, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'], url_path='bulk-update-property')
    def bulk_update_property(self, request):
        supplypoint_permissions = PermissionManager.get_model_permissions(request.user, 'supplypoint', 'service')
        if not supplypoint_permissions['can_change']:
            return Response({"error": "Insufficient permissions to update supply points"}, status=status.HTTP_403_FORBIDDEN)
        
        data = request.data
        if not isinstance(data, list):
            return Response({"error": "Expected a list of property updates"}, status=status.HTTP_400_BAD_REQUEST)
        
        updated_count = 0
        from django.db import transaction
        with transaction.atomic():
            for item in data:
                property_id = item.get('property_id')
                supply_point_ids = item.get('supply_points')
                
                if property_id is None or not isinstance(supply_point_ids, list):
                    continue
                
                try:
                    new_property = Property.objects.get(id=property_id)
                except Property.DoesNotExist:
                    continue
                
                # First, unlink any supply points currently linked to this property but not in the request list
                existing_supply_points = SupplyPoint.objects.filter(property=new_property)
                to_unlink = existing_supply_points.exclude(id__in=supply_point_ids)
                for sp in to_unlink:
                    previous_property = sp.property
                    sp.property = None
                    sp.save()
                    supply_point_change_property(request.user, sp.id, previous_property, None)
                    updated_count += 1
                
                # Next, link new supply points (or update existing ones if they changed)
                supply_points = SupplyPoint.objects.filter(id__in=supply_point_ids)
                for sp in supply_points:
                    if sp.property_id != new_property.id:
                        previous_property = sp.property
                        sp.property = new_property
                        sp.save()
                        supply_point_change_property(request.user, sp.id, previous_property, new_property)
                        updated_count += 1
                
        return Response({"message": f"Successfully updated {updated_count} supply points"}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], url_path='permissions')
    def permissions(self, request):
        pk = request.query_params.get('id')
        if pk:
            from django.contrib.auth.models import Group
            user_permissions = PermissionManager.get_model_permissions(request.user, 'auth', 'group')
            if not user_permissions['can_view'] or not user_permissions['can_change'] or not request.user.is_superuser:
                return Response( None, status=status.HTTP_403_FORBIDDEN )
            group = Group.objects.filter(id=pk).first()
            if not group:
                return Response( None, status=status.HTTP_404_NOT_FOUND )
            group_permissions = PermissionManager.get_model_group_permissions(group, 'supplypoint')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'supplypoint', 'service')
        return Response(permissions, status=status.HTTP_200_OK)
        
    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        elif self.action == 'update_meter':
            return [IsAuthenticated()]
        elif self.action == 'bulk_update_property':
            return [IsAuthenticated()]
        return super().get_permissions()


class SupplyPointActivateView(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = SupplyPoint.objects.all()
    
    def put(self, request, id):
        try:
            supply_point = supply_point_activate(request.user, id)
            serializer = SupplyPointSerializer(supply_point, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except SupplyPoint.DoesNotExist:
            return Response({"error": "SupplyPoint not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SupplyPointDeactivateView(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = SupplyPoint.objects.all()
    
    def put(self, request, id):
        today = timezone.now().date().strftime('%Y-%m-%d')
        removal_at = request.data.get('removal_at', today)
        removal_reason = request.data.get('removal_reason', None)
        
        """ if not removal_at or not removal_reason:
            return Response({"error": "removal_at and removal_reason are required"}, status=status.HTTP_400_BAD_REQUEST) """
        
        try:
            supply_point = supply_point_deactivate(request.user, id, removal_at, removal_reason)
            serializer = SupplyPointSerializer(supply_point, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except SupplyPoint.DoesNotExist:
            return Response({"error": "SupplyPoint not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SupplyPointChangeAddressView(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = SupplyPoint.objects.all()
    
    def put(self, request, id):
        previous_address = request.data.get('previous_address')
        current_address = request.data.get('current_address')
        
        if not previous_address or not current_address:
            return Response({"error": "previous_address and current_address are required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            supply_point = supply_point_change_address(request.user, id, previous_address, current_address)
            serializer = SupplyPointSerializer(supply_point, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except SupplyPoint.DoesNotExist:
            return Response({"error": "SupplyPoint not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
