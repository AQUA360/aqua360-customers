from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from ..models import ClaimRequestStepTemplate
from ..serializers import (
    ClaimRequestStepTemplateSerializer,
    ClaimRequestStepTemplateListSerializer,
    ClaimRequestStepTemplateSaveSerializer
)
from claimrequest.permissions import ClaimRequestPermission
class ClaimRequestStepTemplateViewSet(viewsets.ModelViewSet):
    queryset = ClaimRequestStepTemplate.objects.all().order_by('position')
    serializer_class = ClaimRequestStepTemplateSerializer
    permission_classes = [IsAuthenticated, ClaimRequestPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_fields = ['template']
    search_fields = ['token', 'name']
    ordering_fields = ['token', 'name', 'position', 'duration']
    lookup_field = 'id'
    
    def get_serializer_class(self):
        if self.request.method in ['GET']:
            if self.action == 'list':
                return ClaimRequestStepTemplateListSerializer
            return ClaimRequestStepTemplateSerializer
        return ClaimRequestStepTemplateSaveSerializer 