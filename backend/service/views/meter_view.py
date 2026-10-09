from rest_framework.decorators import action
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.settings import api_settings
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from django.db.models import Subquery, OuterRef, F, Prefetch
from django.core.paginator import Paginator, EmptyPage

from auth.permissions import PermissionManager
from billing.models import Reading
from service.models import Meter, MeterLog, SupplyPoint, MeterStatus
from service.serializers.meter_serializer import (
    MeterReadingDocumentSerializer,
    MeterSerializer,
    MeterListSerializer,
    MeterLogSerializer,
)
from service.filters.meter_filter import MeterFilter
from service.utils.meter_bulk_update_service import (
    MeterBulkUpdateError,
    apply_updates,
    build_preview,
)

class MeterViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Meter to be viewed or edited.
    """
    queryset = Meter.objects.filter(is_active=True)
    serializer_class = MeterSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = MeterFilter
    search_fields = ['code', 'supply_points__address__street__name']
    ordering_fields = [
        'code', 'supply_point_status', 'has_remote_reading', 'created_at',
        'updated_at', 'installation_at', 'status', 'caliber', 'comm_technology',
        'caliber_token', 'manufacturer', 'manufacturing_year',
    ]
    ordering = ['code']

    def get_queryset(self):
        qs = super().get_queryset()

        # Only annotate fields needed for the current ordering (keeps COUNT cheap)
        ordering = self.request.query_params.get('ordering', '') if hasattr(self, 'request') else ''
        ordering_fields = {o.lstrip('-') for o in ordering.split(',') if o} or set(self.ordering or [])

        if 'supply_point_status' in ordering_fields:
            qs = qs.annotate(
                supply_point_status=Subquery(
                    SupplyPoint.objects.filter(meter=OuterRef('pk'))
                    .order_by('id')
                    .values('status__name')[:1]
                )
            )
        if 'caliber_token' in ordering_fields:
            qs = qs.annotate(caliber_token=F('caliber__token'))

        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        meters = list(page) if page is not None else list(queryset)
        meters = self._optimize_list_meters(meters)
        reading_maps = self._bulk_last_readings(meters)
        serializer = self.get_serializer(
            meters,
            many=True,
            context={**self.get_serializer_context(), **reading_maps},
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def _optimize_list_meters(self, meters):
        """Re-fetch the page with joins/prefetches (avoids weighing down COUNT)."""
        if not meters:
            return meters
        meter_ids = [m.id for m in meters]
        optimized = (
            Meter.objects.filter(id__in=meter_ids)
            .select_related(
                'status',
                'caliber',
                'address_street',
                'address_city',
            )
            .prefetch_related(
                Prefetch(
                    'supply_points',
                    queryset=SupplyPoint.objects.select_related(
                        'status',
                        'address',
                        'address__street',
                        'address__street_number',
                        'address__city',
                        'connection',
                        'connection__exploitation',
                    ).order_by('id'),
                ),
            )
        )
        by_id = {m.id: m for m in optimized}
        return [by_id[mid] for mid in meter_ids if mid in by_id]

    def _bulk_last_readings(self, meters):
        """Load last readings for the current page only (2 queries total)."""
        meter_ids = [m.id for m in meters]
        last_reading_by_meter = {}
        last_reading_id_by_meter = {}
        if not meter_ids:
            return {
                'last_reading_by_meter': last_reading_by_meter,
                'last_reading_id_by_meter': last_reading_id_by_meter,
            }

        # Display last reading (same filters as previous serializer)
        display_qs = (
            Reading.objects.filter(
                meter_id__in=meter_ids,
                is_close=False,
                is_control=False,
            )
            .select_related('alert')
            .order_by('meter_id', '-reading_date', '-id')
            .only(
                'id', 'meter_id', 'reading_date', 'reading_value', 'consumption_days',
                'is_estimated', 'contract_request_id', 'is_initial', 'alert_notes',
                'alert__name',
            )
        )
        for reading in display_qs:
            if reading.meter_id not in last_reading_by_meter:
                last_reading_by_meter[reading.meter_id] = reading

        # last_reading_id (is_active=True) — separate rule kept for API compatibility
        active_qs = (
            Reading.objects.filter(meter_id__in=meter_ids, is_active=True)
            .order_by('meter_id', '-reading_date', '-id')
            .only('id', 'meter_id')
        )
        for reading in active_qs:
            if reading.meter_id not in last_reading_id_by_meter:
                last_reading_id_by_meter[reading.meter_id] = reading.id

        return {
            'last_reading_by_meter': last_reading_by_meter,
            'last_reading_id_by_meter': last_reading_id_by_meter,
        }

    def get_serializer_class(self):
        if self.action == 'list':  # Corresponds to GET / (list view)
            return MeterListSerializer
        elif self.action == 'retrieve':  # Corresponds to GET /id (detail view)
            return MeterSerializer
        return super().get_serializer_class()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=False, methods=['get'], url_path='check-code')
    def check_code(self, request):
        code = request.query_params.get('code')
        exclude_id = request.query_params.get('exclude_id')
        if not code:
            return Response({'exists': False})
    
        qs = Meter.objects.filter(code=code)
        if exclude_id:
            qs = qs.exclude(id=exclude_id)
    
        meter = qs.first()
        return Response({
            'exists': meter is not None,
            'meter': {'id': meter.id, 'code': meter.code} if meter else None,
        })
    
    @action(detail=True, methods=['put'], url_path='status')
    def status_update(self, request, pk=None):
        try:
            meter = self.get_object()
            try:
                status_token = request.data.get('status_token')
                meter_status = MeterStatus.objects.get(token=status_token)
                meter.status = meter_status
                meter.save()
                serializer = MeterSerializer(meter)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except Exception as e:
                print(e)
                return Response(
                    {"error": str(e)}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Meter.DoesNotExist:
            return Response(
                {"error": "Meter not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
            
    @action(detail=True, methods=['get'], url_path='logs')
    def logs(self, request, pk=None):
        try:
            meter = self.get_object()
            logs = MeterLog.objects.filter(meter=meter).order_by('-created_at')
            serializer = MeterLogSerializer(logs, many=True, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Meter.DoesNotExist:
            return Response(
                {"error": "Meter not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
            
    @action(detail=False, methods=['post'], url_path='reading-document')
    def get_by_reading_document(self, request, pk=None):
        try:
            from billing.models import Reading
            reading_document = request.data.get('reading_document')
            show_alerts = request.data.get('show_alerts')
            show_remote_alerts = request.data.get('show_remote_alerts')
            search_query = request.data.get('search_query')
            page = request.data.get('page', 1)
            page_size = request.data.get('page_size')
            try:
                page = int(page)
            except (TypeError, ValueError):
                page = 1
            try:
                page_size = int(page_size) if page_size else api_settings.PAGE_SIZE
            except (TypeError, ValueError):
                page_size = api_settings.PAGE_SIZE
                
            readings = Reading.objects.filter(document__id=reading_document).select_related('meter')
            if show_alerts:
                readings = readings.filter(alert__isnull=False)
            if show_remote_alerts:
                readings = readings.filter(remote_alert__isnull=False)
            if search_query and search_query.strip():
                readings = readings.filter(meter__code__icontains=search_query)
            
            meters = []
            for reading in readings:
                meter = reading.meter
                if not meter:
                    continue
                if not hasattr(meter, 'reading_ids'):
                    meters.append(meter)
                    meter.reading_ids = []
                meter.reading_ids.append(reading.id)

            paginator = Paginator(meters, page_size)
            try:
                paginated_meters = paginator.page(page)
            except EmptyPage:
                return Response({"detail": "Invalid page."}, status=status.HTTP_404_NOT_FOUND)
            serializer = MeterReadingDocumentSerializer(
                paginated_meters,
                many=True,
                context={'request': request},
            )
            return Response({
                "count": paginator.count,
                "page": paginated_meters.number,
                "page_size": page_size,
                "total_pages": paginator.num_pages,
                "has_next": paginated_meters.has_next(),
                "has_previous": paginated_meters.has_previous(),
                "next_page": paginated_meters.next_page_number() if paginated_meters.has_next() else None,
                "previous_page": paginated_meters.previous_page_number() if paginated_meters.has_previous() else None,
                "results": serializer.data,
            }, status=status.HTTP_200_OK)
        except Meter.DoesNotExist:
            return Response(
                {"error": "Meter not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
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
            group_permissions = PermissionManager.get_model_group_permissions(group, 'meter')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'meter', 'service')
        return Response(permissions, status=status.HTTP_200_OK)

    def _bulk_update_from_file(self, request, *, apply):
        uploaded = request.FILES.get('file') or request.data.get('file')
        if not uploaded:
            return Response(
                {"error": "Cal enviar el fitxer al camp 'file' (CSV o Excel)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = apply_updates(uploaded) if apply else build_preview(uploaded)
        except MeterBulkUpdateError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=['post'],
        url_path='bulk-update/preview',
        parser_classes=[MultiPartParser, FormParser],
    )
    def bulk_update_preview(self, request):
        """Previsualitza canvis d'update massiva de Meter des de CSV/Excel."""
        return self._bulk_update_from_file(request, apply=False)

    @action(
        detail=False,
        methods=['post'],
        url_path='bulk-update/confirm',
        parser_classes=[MultiPartParser, FormParser],
    )
    def bulk_update_confirm(self, request):
        """Confirma i aplica l'update massiva de Meter (re-upload del mateix fitxer)."""
        return self._bulk_update_from_file(request, apply=True)

    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        # POST custom: DjangoModelPermissions demanaria add_meter; aquí cal change_meter
        if self.action in ('bulk_update_preview', 'bulk_update_confirm'):
            return [IsAuthenticated()]
        return super().get_permissions()

    def check_permissions(self, request):
        super().check_permissions(request)
        if self.action in ('bulk_update_preview', 'bulk_update_confirm'):
            if not request.user.has_perm('service.change_meter'):
                self.permission_denied(request)
