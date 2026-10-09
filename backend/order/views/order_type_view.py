from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from ..models import OrderType
from ..serializers.value_objects_serializer import OrderTypeSerializer
from order.permissions import OrderPermission
class OrderTypeViewSet(viewsets.ModelViewSet):
    queryset = OrderType.objects.all().order_by('token')
    serializer_class = OrderTypeSerializer
    permission_classes = [IsAuthenticated, OrderPermission]
    search_fields = ['token', ]
    ordering_fields = ['token',]