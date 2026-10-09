from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.filters import OrderingFilter

from django.db import transaction
from django.db.models import F, Prefetch, Max
from rest_framework.response import Response

from lecturapp.mixins import LecturappAuthMixin
from service.models import Property, RoutePosition
from service.serializers.route_serializer import RoutePositionAppSerializer, RoutePositionSerializer, RoutePositionListSerializer
from service.filters.route_position_filter import RoutePositionFilter
from django_filters.rest_framework import DjangoFilterBackend
from service.permissions import RoutePermission
from service.utils.property_route_service import sync_property_tokens_with_route_position
from service.utils.route_positions_service import regenerate_route_position_token


class RoutePositionViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Meter to be viewed or edited.
    """
    queryset = RoutePosition.objects.all().order_by('position', 'token')
    serializer_class = RoutePositionSerializer
    permission_classes = [IsAuthenticated, RoutePermission]
    filterset_class = RoutePositionFilter
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    search_fields = ['token', 'name']
    ordering_fields = ['token', 'name', 'reader_observation', 'position']

    def get_serializer_class(self):
        if self.action == 'list':
            return RoutePositionListSerializer
        return RoutePositionSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        # Calculem posicions lliures i última posició
        # Idealment ho fem sobre tota la ruta si tenim el filtre de ruta, 
        # ja que el 'search' podria ocultar posicions ocupades.
        route_id = request.query_params.get('route')
        if route_id:
            positions_qs = RoutePosition.objects.filter(route_id=route_id)
        else:
            positions_qs = queryset

        positions_stats = positions_qs.aggregate(max_pos=Max('position'))
        max_pos = positions_stats['max_pos'] or 1
        
        occupied_positions = set(positions_qs.values_list('position', flat=True))
        available_positions = [i for i in range(1, max_pos + 1) if i not in occupied_positions]

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data['available_positions'] = available_positions
            response.data['last_position'] = max_pos
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'results': serializer.data,
            'available_positions': available_positions,
            'last_position': max_pos
        })

    @action(detail=False, methods=['get'])
    def check_position(self, request):
        """
        Comprova si una posició concreta ja està ocupada dins una ruta,
        sense necessitat de carregar totes les posicions de la ruta.

        Query params: ?route=<id>&position=<int>
        """
        route_id = request.query_params.get('route')
        position = request.query_params.get('position')

        if route_id is None or position is None:
            return Response(
                {'detail': 'route i position són obligatoris.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            route_id = int(route_id)
            position = int(position)
        except (TypeError, ValueError):
            return Response(
                {'detail': 'route i position han de ser enters.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        occupied = RoutePosition.objects.filter(route_id=route_id, position=position).exists()
        return Response({'position': position, 'occupied': occupied})

    @action(detail=True, methods=['post'])
    def move(self, request, pk=None):
        """
        Mou una posició existent a una nova posició dins la ruta, desplaçant
        atòmicament les posicions intermèdies +1 o -1 segons la direcció.

        Body: { "new_position": <int>, "route_id": <int> }
        """
        route_position = self.get_object()
        new_position = request.data.get('new_position')
        route_id = request.data.get('route_id')

        if new_position is None or route_id is None:
            return Response(
                {'detail': 'new_position i route_id són obligatoris.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            new_position = int(new_position)
            route_id = int(route_id)
        except (TypeError, ValueError):
            return Response(
                {'detail': 'new_position i route_id han de ser enters.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_position = route_position.position

        if new_position == old_position:
            serializer = self.get_serializer(route_position)
            return Response(serializer.data)

        with transaction.atomic():
            if new_position < old_position:
                # Moviment cap amunt: desplacem +1 les posicions en [new, old-1]
                shifted_qs = RoutePosition.objects.filter(
                    route_id=route_id,
                    position__gte=new_position,
                    position__lt=old_position,
                ).exclude(pk=route_position.pk)
                shifted_ids = list(shifted_qs.values_list('pk', flat=True))
                shifted_qs.update(position=F('position') + 1)
            else:
                # Moviment cap avall: desplacem -1 les posicions en [old+1, new]
                shifted_qs = RoutePosition.objects.filter(
                    route_id=route_id,
                    position__gt=old_position,
                    position__lte=new_position,
                ).exclude(pk=route_position.pk)
                shifted_ids = list(shifted_qs.values_list('pk', flat=True))
                shifted_qs.update(position=F('position') - 1)

            route_position.position = new_position
            route_position.save()

        route_position.refresh_from_db()
        regenerate_route_position_token(route_position)
        sync_property_tokens_with_route_position(route_position)
        # El desplaçament de les posicions veïnes es fa amb un update() de
        # queryset (bulk), que no torna a carregar els objectes ni recalcula
        # tokens per si sol: cal regenerar-los i sincronitzar-los explícitament un a un.
        for shifted_id in shifted_ids:
            shifted_position = RoutePosition.objects.get(pk=shifted_id)
            regenerate_route_position_token(shifted_position)
            sync_property_tokens_with_route_position(shifted_position)

        serializer = self.get_serializer(route_position)
        return Response(serializer.data)

class RoutePositionAppViewSet(LecturappAuthMixin, viewsets.ModelViewSet):
    """
    API endpoint that allows Meter to be viewed or edited.
    """
    queryset = RoutePosition.objects.all().order_by('position', 'token')
    serializer_class = RoutePositionAppSerializer
    permission_classes = [AllowAny] 
    filterset_class = RoutePositionFilter
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    search_fields = ['token', 'name']
    ordering_fields = ['token', 'name']

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.prefetch_related(
            Prefetch('properties', queryset=Property.objects.order_by('-token'))
        )
        return queryset
