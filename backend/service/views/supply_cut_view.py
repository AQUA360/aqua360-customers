from rest_framework.decorators import action
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from service.filters.supply_cut_filter import SupplyCutFilter, SupplyCutOrderingFilter
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from auth.permissions import PermissionManager
from logger.models import LogSupplyCutStatus
from service.models import SupplyCut, SupplyCutCause, SupplyCutStatus, SupplyPoint
from service.serializers.supply_cut_serializer import SupplyCutSerializer, SupplyCutMinimalSerializer
from service.utils import supply_cut_service


class SupplyCutViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows SupplyCut to be viewed or edited.
    """
    queryset = SupplyCut.objects.all().prefetch_related(
        Prefetch(
            'supply_points__supply_cuts',
            queryset=SupplyCut.objects.select_related('status', 'cause').order_by('-id'),
            to_attr='_prefetched_supply_cuts',
        )
    ).order_by('status', 'date_start', '-id')
    serializer_class = SupplyCutSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filterset_class = SupplyCutFilter
    search_fields = [
        'token',
        'supply_points__token',
        'supply_points__address__street__name',
        'supply_points__contracts__token',
        'supply_points__contracts__holder__name',
        'supply_points__contracts__holder__surname',
        'supply_points__default_contracts__token',
        'supply_points__default_contracts__holder__name',
        'supply_points__default_contracts__holder__surname',
    ]
    filter_backends = [DjangoFilterBackend, SupplyCutOrderingFilter, SearchFilter]
    # This view is the only one that uses the dict form: the frontend list
    # sorts by the `status_name` column, which maps to the model field
    # `status__name`.
    ordering_fields = {
        'id': 'id',
        'token': 'token',
        'source': 'source',
        'date_start': 'date_start',
        'date_end': 'date_end',
        'exec_start': 'exec_start',
        'exec_end': 'exec_end',
        'status_name': 'status__name',
    }

    @action(detail=False, methods=['get'], url_path='list')
    def simple_list(self, request):
        qs = self.get_queryset().select_related('status', 'cause').prefetch_related(
            Prefetch(
                'supply_points',
                queryset=SupplyPoint.objects.select_related('address__street__type'),
                to_attr='_prefetched_supply_points',
            )
        )
        # filter_queryset already applies the `ordering` param. Only fall
        # back to the module default when no explicit ordering is requested,
        # otherwise `order_by('-date_end')` would silently override the
        # column the user asked to sort by (e.g. the ID column).
        queryset = self.filter_queryset(qs)
        if 'ordering' not in request.query_params:
            queryset = queryset.order_by('-date_end')
        paginator = PageNumberPagination()
        paginator.page_size = 50
        result_page = paginator.paginate_queryset(queryset, request)
        serializer = SupplyCutMinimalSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = SupplyCutSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = SupplyCutSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data)
    
    @action(detail=True, methods=['post'], url_path='resolve-review')
    def resolve_review(self, request, pk=None):
        """Resol una quarantena (requires_review): assigna l'estat real
        (0..3, mai Conflicte) i esborra la marca, propagant-ho als PP amb la
        mateixa màquina d'estats (un tall que queda Actiu i és indefinit es
        talla; un que tanca restaura). `cause_raw`/`state_raw` es conserven
        com a traça de la revisió."""
        supply_cut = self.get_object()
        if not supply_cut.requires_review:
            return Response(
                {'status': 'error', 'message': 'El tall no requereix revisió.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        status_token = request.data.get('status')
        if status_token not in ('0', '1', '2', '3'):
            return Response(
                {'status': 'error', 'message': 'Estat de destí no vàlid.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        target_status = SupplyCutStatus.objects.get(token=status_token)
        previous_status = supply_cut.status
        observation = request.data.get('observation')

        if 'cause' in request.data:
            try:
                supply_cut.cause = SupplyCutCause.objects.get(id=request.data['cause'])
            except SupplyCutCause.DoesNotExist:
                return Response(
                    {'status': 'error', 'message': 'Causa no vàlida.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        supply_cut.status = target_status
        supply_cut.requires_review = False
        for field in ('date_start', 'date_end', 'exec_start', 'exec_end'):
            if field in request.data:
                setattr(supply_cut, field, request.data[field])
        supply_cut.save()

        supply_cut_service.sync_supply_points_status(
            supply_cut,
            previous_status=previous_status,
            user=request.user,
            observation=observation,
        )
        LogSupplyCutStatus.objects.create(
            object=supply_cut,
            previous_status=previous_status,
            current_status=target_status,
            user=request.user,
            observation=observation,
        )
        serializer = SupplyCutSerializer(supply_cut, context=self.get_serializer_context())
        return Response(
            {
                'check_response': {'status': 'success', 'message': 'Revisió resolta.'},
                **serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'], url_path='remove-supply-point')
    def remove_supply_point(self, request, pk=None):
        """Removes one or more supply points from the cut and restores them.

        This is how a cut stops affecting a specific contract without closing
        the whole cut. If the cut ends up with no points, it is closed.
        """
        supply_cut = self.get_object()

        supply_point_ids = request.data.get('supply_points')
        if not supply_point_ids:
            single = request.data.get('supply_point')
            supply_point_ids = [single] if single else []
        supply_point_ids = [spid for spid in supply_point_ids if spid]

        if not supply_point_ids:
            return Response(
                {'status': 'error', 'message': "Cal indicar 'supply_point' o 'supply_points'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        observation = request.data.get('observation')
        restored = supply_cut_service.remove_supply_points_from_cut(
            supply_cut, supply_point_ids, user=request.user, observation=observation
        )

        # A cut with no points no longer affects anyone: it is closed so that it
        # does not stay open forever nor get reactivated by the scheduled tasks.
        if not supply_cut.supply_points.exists() and not supply_cut_service.is_supply_cut_closed(supply_cut):
            previous_status = supply_cut.status
            closed_status = SupplyCutStatus.objects.get(token=supply_cut_service.closed_status_token())
            supply_cut.status = closed_status
            supply_cut.save(update_fields=['status', 'updated_at'])
            supply_cut_service.close_supply_cut(supply_cut, user=request.user, observation=observation)
            LogSupplyCutStatus.objects.create(
                object=supply_cut,
                previous_status=previous_status,
                current_status=closed_status,
                user=request.user,
                observation=observation,
            )

        supply_cut.refresh_from_db()
        serializer = SupplyCutSerializer(supply_cut, context=self.get_serializer_context())
        return Response(
            {
                'check_response': {
                    'status': 'success',
                    'message': f"{len(supply_point_ids)} punt(s) tret(s) del tall, {restored} restablert(s).",
                },
                **serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'], url_path='start-cut')
    def start_cut(self, request, pk=None):
        """Inicia un tall PLANIFICAT: passa a Actiu, stampa exec_start i, si és
        indefinit, talla els punts. Un accident/previst temporal s'activa sense
        tocar els PP."""
        supply_cut = self.get_object()
        previous_status = supply_cut.status
        observation = request.data.get('observation')
        try:
            started = supply_cut_service.start_cut(
                supply_cut, user=request.user, observation=observation
            )
        except ValueError as exc:
            return Response(
                {'status': 'error', 'message': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        LogSupplyCutStatus.objects.create(
            object=started,
            previous_status=previous_status,
            current_status=started.status,
            user=request.user,
            observation=observation,
        )
        serializer = SupplyCutSerializer(started, context=self.get_serializer_context())
        return Response(
            {
                'check_response': {'status': 'success', 'message': 'Tall iniciat.'},
                **serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'], url_path='finish-cut')
    def finish_cut(self, request, pk=None):
        """Finalitza un tall ACTIU: passa a Acabat, stampa exec_end i restaura
        els punts. Un tall mai Actiu no pot acabar: es cancel·la."""
        supply_cut = self.get_object()
        previous_status = supply_cut.status
        observation = request.data.get('observation')
        try:
            finished = supply_cut_service.finish_cut(
                supply_cut, user=request.user, observation=observation
            )
        except ValueError as exc:
            return Response(
                {'status': 'error', 'message': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        LogSupplyCutStatus.objects.create(
            object=finished,
            previous_status=previous_status,
            current_status=finished.status,
            user=request.user,
            observation=observation,
        )
        serializer = SupplyCutSerializer(finished, context=self.get_serializer_context())
        return Response(
            {
                'check_response': {'status': 'success', 'message': 'Tall finalitzat.'},
                **serializer.data,
            },
            status=status.HTTP_200_OK,
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
            group_permissions = PermissionManager.get_model_group_permissions(group, 'supplycut')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'supplycut', 'service')
        return Response(permissions, status=status.HTTP_200_OK)
        
    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()