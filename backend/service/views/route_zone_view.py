from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from service.models import RouteZone
from service.serializers.route_serializer import RouteZoneSerializer
from service.filters.route_zone_filter import RouteZoneFilter
from service.permissions import RoutePermission

class RouteZoneViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Zone to be viewed or edited.
    """
    queryset = RouteZone.objects.all().order_by('token')
    serializer_class = RouteZoneSerializer
    filterset_class = RouteZoneFilter
    permission_classes = [IsAuthenticated, RoutePermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    ordering_fields = ['token', 'name']
