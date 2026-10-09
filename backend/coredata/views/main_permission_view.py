from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from coredata.models import MainPermission
from coredata.serializers import MainPermissionSerializer
from pagination.large_pagination import LargeResultsSetPagination
class MainPermissionViewSet(viewsets.ModelViewSet):
    queryset = MainPermission.objects.all().order_by('name')
    serializer_class = MainPermissionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields = ['name']
    ordering_fields = ['name']
    pagination_class = LargeResultsSetPagination
