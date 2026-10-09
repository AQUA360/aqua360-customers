from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from ..models import Publication
from ..serializers.publication_serializer import PublicationSerializer
from pricing.permissions import PriceRatePermission
from django_filters.rest_framework import DjangoFilterBackend
from ..filters.publication_filter import PublicationFilter

class PublicationViewSet(viewsets.ModelViewSet):
    queryset = Publication.objects.all().order_by('-created_at')
    serializer_class = PublicationSerializer
    permission_classes = [IsAuthenticated, PriceRatePermission]
    filterset_class = PublicationFilter
    filter_backends = [DjangoFilterBackend]