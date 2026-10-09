from rest_framework import status
from rest_framework.decorators import action
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from ..models import (ProductOrigin )
from ..serializers.value_objects_serializer import ProductOriginSerializer
from pricing.permissions import ProductPermission
class ProductOriginViewSet(viewsets.ModelViewSet):
    queryset = ProductOrigin.objects.all().order_by('id')
    serializer_class = ProductOriginSerializer
    permission_classes = [IsAuthenticated, ProductPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    search_fields = '__all__'
    ordering_fields = '__all__'
    