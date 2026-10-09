from datetime import timedelta
from rest_framework.decorators import action
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.pagination import PageNumberPagination
from django.db.models import Case, When, Value, IntegerField, F, Q, CharField
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.db import transaction
from ..services.change_meter import OrderChangeMeterValidationService

from ..models import Order
from ..serializers.order_serializer import OrderSerializer, OrderListSerializer, OrderSaveSerializer
from ..filters.order_filter import OrderFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from auth.permissions import PermissionManager
from coredata.models import City
from coredata.serializers import CityMinimalSerializer

class OrderViewSet(viewsets.ModelViewSet):
    
    queryset = (
        Order.objects.annotate(
            # Use priority position for sorting (default to 0 if null)
            priority_value=Case(
                When(priority__position__isnull=False, then=F('priority__position')),
                default=Value(0),
                output_field=IntegerField()
            ),
            # Create sort key: completed orders go last
            is_completed=Case(
                When(completed_at__isnull=True, then=Value(0)),  # Not completed = 0 (first)
                default=Value(1),  # Completed = 1 (last)
                output_field=IntegerField()
            ),
            related_contract_token=Coalesce(
                'contract__token',
                'contract_request__token',
                'contract_termination_request__token',
                'claim_request__token',
                output_field=CharField()
            )
        )
        .order_by(
            'is_completed',      # 1. Uncompleted orders first
            'dueDateAt',         # 2. Oldest due date first (nulls last by default in PostgreSQL)
            '-created_at',       # 4. Newer orders first as tiebreaker
            '-priority_value'    # 3. Higher priority first
        )
    )
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = OrderFilter
    search_fields = ['token', 'operators__name', 'type__name', 'related_contract_token']
    ordering_fields = ['token', 'status', 'created_at', 'completed_at', 'dueDateAt', 'priority__position', 'contract__token', 'related_contract_token', 'created_by']
    
    @action(detail=False, methods=['get'], url_path='list')
    def simple_list(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        paginator = PageNumberPagination()
        paginator.page_size = 50
        result_page = paginator.paginate_queryset(queryset, request)
        serializer = OrderListSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='filter-cities')
    def filter_cities(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        city_ids = set()
        for path in [
            'address__city_id',
            'contract__supply_point_default__address__city_id',
            'contract_request__supply_point_default__address__city_id',
            'supply_point__address__city_id',
            'connection__address_city_id',
            'connection_request__address_city_id',
        ]:
            city_ids.update(
                queryset.exclude(**{path: None}).values_list(path, flat=True)
            )
        cities = City.objects.filter(id__in=city_ids).order_by('name')
        serializer = CityMinimalSerializer(cities, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='preview-change-meter')
    def preview_change_meter(self, request, pk=None):
        order = self.get_object()
        service = OrderChangeMeterValidationService(order)
        return Response(service.preview(), status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='by-token/(?P<token>[^/.]+)')
    def by_token(self, request, token=None):
        try:
            order = Order.objects.get(token=token)
            serializer = self.get_serializer(order)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found"}, 
                status=status.HTTP_204_NO_CONTENT
            )
        
    def get_serializer_class(self):
        if self.action == 'list':  
            return OrderListSerializer
        elif self.action == 'retrieve':
            return OrderSerializer
        return OrderSaveSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = OrderSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers, content_type='application/json')

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = OrderSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_200_OK, content_type='application/json')
    
    @action(detail=False, methods=['get'], url_path='permissions')
    def permissions(self, request):
        pk = request.query_params.get('id')
        if pk:
            from django.contrib.auth.models import Group
            user_permissions = PermissionManager.get_model_permissions(request.user, 'order', 'order')
            if not user_permissions['can_view'] or not user_permissions['can_change'] or not request.user.is_superuser:
                return Response( None, status=status.HTTP_403_FORBIDDEN )
            group = Group.objects.filter(id=pk).first()
            if not group:
                return Response( None, status=status.HTTP_404_NOT_FOUND )
            group_permissions = PermissionManager.get_model_group_permissions(group, 'order')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'order', 'order')
        return Response(permissions, status=status.HTTP_200_OK)
        
    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()

    @action(detail=True, methods=['get'], url_path='validate-change-meter')
    def validate_change_meter(self, request, pk=None):
        order = self.get_object()
        service = OrderChangeMeterValidationService(order)
        return Response(service.validate(), status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='apply-change-meter')
    def apply_change_meter(self, request, pk=None):
        order = self.get_object()
        service = OrderChangeMeterValidationService(order)
        try:
            result = service.apply(user=request.user)
        except ValueError as e:
            return Response(
                {'applied': False, 'missing_fields': e.args[0]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from ..tasks import create_change_meter_notification
        transaction.on_commit(lambda: create_change_meter_notification.delay(order.id, order.token))

        return Response(result, status=status.HTTP_200_OK)