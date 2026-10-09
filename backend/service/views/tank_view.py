from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from service.models import Tank
from service.serializers.tank_serializer import TankSerializer 
from service.permissions import ConnectionPermission

class TankViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows DMA to be viewed or edited.
    """
    queryset = Tank.objects.all().order_by('token')
    serializer_class = TankSerializer
    permission_classes = [IsAuthenticated, ConnectionPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    ordering_fields = ['token', 'name']
