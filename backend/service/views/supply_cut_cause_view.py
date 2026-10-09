from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from service.serializers.supply_cut_serializer import SupplyCutCauseSerializer

from service.models import (SupplyCutCause )
from service.permissions import SupplyCutPermission

class SupplyCutCauseViewSet(viewsets.ModelViewSet):
    queryset = SupplyCutCause.objects.all()
    serializer_class = SupplyCutCauseSerializer
    filter_backends = (DjangoFilterBackend,)
    permission_classes = [IsAuthenticated, SupplyCutPermission]