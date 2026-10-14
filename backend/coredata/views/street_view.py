from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from coredata.models import Street, StreetType
from coredata.serializers import StreetSerializer, StreetTypeSerializer
from coredata.filters.street_filter import StreetFilter
from coredata.permissions import AddressPermission

from rest_framework.decorators import action
from rest_framework.response import Response
from auth.permissions import PermissionManager

class StreetViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Street to be viewed or edited.
    """
    queryset = Street.objects.all().select_related('city', 'type').order_by('name', 'name_2', 'type')
    serializer_class = StreetSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions | AddressPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = StreetFilter
    search_fields = ['name', 'name_2', 'type__name', 'type__abbreviation']
    ordering_fields = ['id', 'name', 'type__name', 'type__abbreviation', 'city__name']

    @action(detail=False, methods=['get'], url_path='permissions')
    def permissions(self, request):
        permissions = PermissionManager.get_model_permissions(request.user, 'street', 'coredata')
        return Response(permissions)

    @action(detail=False, methods=['post'], url_path='resolve-ids')
    def resolve_ids(self, request):
        """Resolve a list of street ids to their display labels.

        Used by the bulk supply-cut planner so a pasted/uploaded list of ids
        can be sanity-checked (chips) before the preview step. Street names
        collide in ~30% of rows, so ids are the only safe key — this endpoint
        just makes them human-readable again.
        """
        ids = request.data.get('ids')
        if not isinstance(ids, list):
            return Response({'error': "El camp 'ids' ha de ser una llista."}, status=400)
        clean_ids = []
        for value in ids:
            text = str(value).strip() if value is not None else ''
            if text.isdigit():
                clean_ids.append(int(text))
        streets = Street.objects.filter(id__in=clean_ids).select_related('city', 'type')
        data = [
            {
                'id': street.id,
                'label': str(street),
                'city': street.city.name if street.city else '',
            }
            for street in streets
        ]
        return Response({'streets': data}, status=200)

    def get_permissions(self):
        if self.action in ('permissions', 'resolve_ids'):
            return [IsAuthenticated()]
        return super().get_permissions()

class StreetTypeViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows StreetType to be viewed or edited.
    """
    queryset = StreetType.objects.all().order_by('abbreviation')
    serializer_class = StreetTypeSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions | AddressPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields = ['name', 'abbreviation']
    ordering_fields =  ['name', 'abbreviation']

    @action(detail=False, methods=['get'], url_path='permissions')
    def permissions(self, request):
        permissions = PermissionManager.get_model_permissions(request.user, 'streettype', 'coredata')
        return Response(permissions)

    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()
