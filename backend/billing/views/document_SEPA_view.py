from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from billing.models import DocumentSEPA
from billing.serializers.document_SEPA_serializer import DocumentSEPASerializer
from billing.filter.document_sepa_filter import DocumentSEPAFilter
from billing.permissions import PaymentPermission

class DocumentSEPAViewSet(viewsets.ModelViewSet):
    queryset = DocumentSEPA.objects.all()
    serializer_class = DocumentSEPASerializer
    permission_classes = [IsAuthenticated, PaymentPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = DocumentSEPAFilter
    search_fields = '__all__'
    ordering_fields = '__all__'
