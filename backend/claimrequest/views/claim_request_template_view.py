from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from ..models import ClaimRequestTemplate
from ..serializers import ClaimRequestTemplateSerializer
from claimrequest.permissions import ClaimRequestPermission
class ClaimRequestTemplateViewSet(viewsets.ModelViewSet):
    queryset = ClaimRequestTemplate.objects.all()
    serializer_class = ClaimRequestTemplateSerializer
    permission_classes = [IsAuthenticated, ClaimRequestPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields = ['token', 'name']
    ordering_fields = ['token', 'name', 'created_at']
    lookup_field = 'id' 