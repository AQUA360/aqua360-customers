from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from service.models import DMA
from service.serializers.DMA_serializer import DMASerializer
from service.filters.dma_filter import DMAFilter
from service.permissions import ConnectionPermission

class DMAViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows DMA to be viewed or edited.
    """
    queryset = DMA.objects.all().order_by('token')
    serializer_class = DMASerializer
    permission_classes = [IsAuthenticated, ConnectionPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = DMAFilter
    search_fields = ['token', 'name']
    ordering_fields = ['token', 'name']
