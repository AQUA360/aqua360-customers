from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from django.http import HttpResponse
from django.db.models.functions import Coalesce

from auth.permissions import PermissionManager
from service.models import Route
from service.serializers.route_serializer import RouteSerializer, RouteListSerializer
from service.filters.route_filter import RouteFilter
from service.utils import route_bulk_service


class RouteSupplyPointsPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 200


class RouteViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Route to be viewed or edited.
    """
    queryset = Route.objects.all().filter(is_active=True)
    serializer_class = RouteSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = RouteFilter
    search_fields = ['token', 'name']
    ordering_fields = ['token', 'name', 'route_zone']

    def get_serializer_class(self):
        if self.action == 'list':  # Corresponds to GET / (list view)
            return RouteListSerializer
        elif self.action == 'retrieve':  # Corresponds to GET /id (detail view)
            return RouteSerializer
        return super().get_serializer_class()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='permissions')
    def permissions(self, request):
        pk = request.query_params.get('id')
        if pk:
            from django.contrib.auth.models import Group
            user_permissions = PermissionManager.get_model_permissions(request.user, 'auth', 'group')
            if not user_permissions['can_view'] or not user_permissions['can_change'] or not request.user.is_superuser:
                return Response(None, status=status.HTTP_403_FORBIDDEN)
            group = Group.objects.filter(id=pk).first()
            if not group:
                return Response(None, status=status.HTTP_404_NOT_FOUND)
            group_permissions = PermissionManager.get_model_group_permissions(group, 'route')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'route', 'service')
        return Response(permissions, status=status.HTTP_200_OK)

    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        if self.action in ('add_street_preview', 'add_street'):
            # Afegir un carrer modifica una ruta existent: cal permís de modificar
            # rutes (DjangoModelPermissions demanaria el d'afegir en un POST).
            return [IsAuthenticated()]
        return super().get_permissions()

    def _can_change_routes(self, request):
        return PermissionManager.get_model_permissions(request.user, 'route', 'service')['can_change']

    @action(detail=True, methods=['post'], url_path='add-street/preview')
    def add_street_preview(self, request, pk=None):
        """Previsualitza les posicions que es crearien en afegir un carrer."""
        if not self._can_change_routes(request):
            return Response(None, status=status.HTTP_403_FORBIDDEN)
        route = self.get_object()
        try:
            params = route_bulk_service.parse_add_street_params(request.data)
            plan = route_bulk_service.build_add_street_plan(route, params)
        except route_bulk_service.RouteBulkError as e:
            return Response({'detail': e.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(route_bulk_service.serialize_add_street_plan(plan))

    @action(detail=True, methods=['post'], url_path='add-street')
    def add_street(self, request, pk=None):
        """Afegeix a la ruta les finques d'un carrer (una posició per número
        o per finca), desplaçant les posicions posteriors si cal."""
        if not self._can_change_routes(request):
            return Response(None, status=status.HTTP_403_FORBIDDEN)
        route = self.get_object()
        try:
            params = route_bulk_service.parse_add_street_params(request.data)
            plan = route_bulk_service.build_add_street_plan(route, params)
        except route_bulk_service.RouteBulkError as e:
            return Response({'detail': e.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(route_bulk_service.apply_add_street_plan(plan))

    @action(detail=False, methods=['get'], url_path='import/template')
    def import_template(self, request):
        response = HttpResponse(
            route_bulk_service.build_import_template(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="route_import_template.xlsx"'
        return response

    def _import_plan(self, request):
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            raise route_bulk_service.RouteBulkError("Cal adjuntar un fitxer.")
        mode = request.data.get('mode') or route_bulk_service.MODE_APPEND
        rows = route_bulk_service.read_import_file(uploaded_file)
        return route_bulk_service.build_import_plan(rows, mode)

    @action(detail=False, methods=['post'], url_path='import/preview',
            parser_classes=[MultiPartParser, FormParser, JSONParser])
    def import_preview(self, request):
        try:
            plan = self._import_plan(request)
        except route_bulk_service.RouteBulkError as e:
            return Response({'detail': e.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(route_bulk_service.serialize_import_plan(plan))

    @action(detail=False, methods=['post'], url_path='import/confirm',
            parser_classes=[MultiPartParser, FormParser, JSONParser])
    def import_confirm(self, request):
        try:
            plan = self._import_plan(request)
        except route_bulk_service.RouteBulkError as e:
            return Response({'detail': e.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(route_bulk_service.apply_import_plan(plan))

    @action(detail=True, methods=['post'], url_path='export-positions')
    def export_positions(self, request, pk=None):
        route = self.get_object()
        from service.tasks import export_route_positions_csv_task
        task = export_route_positions_csv_task.delay(route.id)
        return Response({
            "task_id": task.id,
            "status": "pending",
            "message": "L'exportació de les posicions de la ruta s'ha encuat correctament."
        }, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['post'], url_path='export-supply-points')
    def export_supply_points(self, request, pk=None):
        route = self.get_object()
        from service.tasks import export_route_supply_points_csv_task
        task = export_route_supply_points_csv_task.delay(route.id)
        return Response({
            "task_id": task.id,
            "status": "pending",
            "message": "L'exportació dels punts de subministrament de la ruta s'ha encuat correctament."
        }, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['get'], url_path='supply-points')
    def supply_points(self, request, pk=None):
        """
        Llistat paginat de SupplyPoints de la Route (tab), alineat amb l'export CSV.
        Filtres: status, contract_status (ids separats per coma).
        Ordenació: property__token, token, status__name|token, contracts__status__name|token
        (prefix '-' per descendent).
        """
        from service.filters.route_supply_point_tab_filter import RouteSupplyPointTabFilter
        from service.serializers.route_supply_point_tab_serializer import RouteSupplyPointTabSerializer
        from service.utils.supply_points_route_csv_export import get_supply_points_for_route

        route = self.get_object()
        queryset = get_supply_points_for_route(route)

        filterset = RouteSupplyPointTabFilter(request.query_params, queryset=queryset)
        queryset = filterset.qs

        ordering = request.query_params.get('ordering')
        allowed_ordering = {
            'property__token',
            '-property__token',
            'token',
            '-token',
            'status__name',
            '-status__name',
            'status__token',
            '-status__token',
            'contracts__status__name',
            '-contracts__status__name',
            'contracts__status__token',
            '-contracts__status__token',
        }
        if ordering and ordering in allowed_ordering:
            # Contract status: distinct per no duplicar files en joins M2M
            if 'contracts__status' in ordering:
                queryset = queryset.order_by(ordering, 'id').distinct()
            else:
                queryset = queryset.order_by(ordering, 'id')
        else:
            queryset = queryset.annotate(
                effective_position=Coalesce('route_position__position', 'property__route_position__position'),
            ).order_by(
                'effective_position',
                'property__token',
                'token',
                'id',
            )

        paginator = RouteSupplyPointsPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = RouteSupplyPointTabSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
