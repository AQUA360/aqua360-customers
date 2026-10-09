from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

#from coredata.filters import PersonDeliquencyFilter
from coredata.models import PersonDeliquency
from coredata.serializers import PersonDeliquencySerializer
from pagination.large_pagination import LargeResultsSetPagination
from coredata.permissions import PersonPermission

class PersonDeliquencyViewSet(viewsets.ModelViewSet):
    
    queryset = PersonDeliquency.objects.all()
    serializer_class = PersonDeliquencySerializer
    permission_classes = [IsAuthenticated, PersonPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    #filterset_class = PersonDeliquencyFilter
    search_fields = ['name', 'country']
    ordering_fields = ['name']
    pagination_class = LargeResultsSetPagination
